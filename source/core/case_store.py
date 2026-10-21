# -*- coding: utf-8 -*-
"""本地学习案例库 (方案A: 外挂案例, 不改动大模型权重)
每条案例: 时刻/物料/工况快照/建议来源(manual|ai|pid)/动作/原因/60秒(仿真时基)后效果
- 动作执行后延迟评估: 相关回路偏差是否收敛 (good/neutral/bad), 或被拒绝(rejected)
- similar(): 同物料 + 关键变量欧氏距离检索最相似的好案例, 注入 LLM 提示词供参考
- export_csv(): 导出扁平 CSV
存储: cases.jsonl, 每行一条 JSON (追加写, 断电不丢)
"""
import csv
import json
import math
import os
import threading
import time
import uuid

from .config import CASE_FILE

EVAL_AFTER_S = 60.0      # 动作后多少仿真秒评估效果
MAX_CASES = 4000         # 文件行数上限, 超出丢弃最旧的 20%

# cases.csv 中文列名 (扁平化, Excel 友好)
# 字段语义:
#   建议值    = ai/pid 给出的目标值 (manual 手动操作无建议, 留空)
#   当前值    = 操作前的 MV (操作前快照)
#   实际下发值 = 操作后真正写下去的值 (AI 方向翻转时与建议值不同)
#   原始建议值 = AI 翻转场景下的 AI 原始输出 (仅 flipped 行有值)
CSV_COLS = ["时间", "来源", "结果", "设备", "参数", "建议值", "当前值", "理由",
            "效果", "拒绝原因",
            "前_塔顶温度", "前_塔釜温度", "前_塔压", "前_回流阀", "前_再沸器功率",
            "后_塔顶温度", "后_塔釜温度", "后_塔压", "后_回流阀", "后_再沸器功率",
            "期望方向", "方向是否正确",
            # 人工审核闭环处置: adopted=直接采纳, flipped=方向翻转后采纳,
            # rejected_magnitude=幅度过大拦截, ignored=用户忽略; manual/pid 留空
            "审核结论", "原始建议值", "实际下发值"]
_VMAP = ["T101.temp", "E102.temp", "T101.press", "FV104.opening", "E102.power"]

# CSV 展示用中文映射 (jsonl 内保留英文枚举, RAG 检索依赖 outcome=="good")
OUTCOME_CN = {"pending": "待评估", "rejected": "已拒绝", "good": "有效",
              "neutral": "中性", "bad": "无效"}

# 相似度用的关键变量 (dev.field) 与归一化尺度
KEY_VARS = [
    ("T101", "temp", 20.0), ("E102", "temp", 20.0),
    ("T101", "press", 20.0), ("V102", "level", 30.0),
    ("V104", "level", 30.0), ("V101", "level", 30.0),
    ("FV102", "opening", 50.0), ("E102", "power", 50.0),
    ("FV103", "opening", 50.0), ("FV104", "opening", 50.0),
    ("FV105", "opening", 50.0), ("FV106", "opening", 50.0),
]


def material_name(st):
    return st.material.name if getattr(st, "material", None) else ""


def snapshot(st):
    """精简工况快照"""
    d = st.devices
    vars_ = {}
    for dev_id, field, _scale in KEY_VARS:
        vars_[f"{dev_id}.{field}"] = round(float(getattr(d[dev_id], field)), 2)
    return {"material": material_name(st), "sim_time": round(st.sim_time, 1), "vars": vars_}


class CaseStore:
    def __init__(self, path=CASE_FILE):
        self.path = path
        self.pending = []        # [{rec, due_time, before_score, lid}]
        self._lock = threading.RLock()   # 保护 jsonl 读写 (UI线程/实验线程可能并发)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 单调序号: 同一秒内多条记录也能保证落盘顺序与执行顺序一致
        self._seq = 0
        for r in self._load_all():
            self._seq = max(self._seq, int(r.get("seq", 0)))

    # ---------- 写入 ----------
    def _upsert(self, rec):
        """按 rid 插入新行或更新已有行; 全文件按 (时间, 序号) 排序后原子重写。
        动作执行时即落盘(pending), 60s 评估后更新同一行 —— 文件顺序始终等于
        执行时间顺序, 不会因延迟评估出现时间戳乱序。"""
        with self._lock:
            rows = self._load_all()
            idx = next((i for i, r in enumerate(rows) if r.get("rid") == rec["rid"]),
                       None)
            if idx is None:
                rows.append(rec)
            else:
                rows[idx] = rec
            rows.sort(key=lambda r: (r.get("t", ""), int(r.get("seq", 0))))
            if len(rows) > MAX_CASES:
                rows = rows[-int(MAX_CASES * 0.8):]
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)   # 原子替换, 防止读到半写文件
            self._sync_csv()

    @staticmethod
    def _expected_direction(loop_mgr, st, action):
        """根据回路 SP-PV 偏差 + 回路作用方向, 判定期望的 MV 动作方向。
        direction=+1 正作用(MV↑→PV↑); direction=-1 反作用(MV↑→PV↓)。
        返回 increase/decrease/hold, 是 MV(执行器) 的期望方向。"""
        if loop_mgr is None:
            return "hold"
        lid = action.get("lid", "")
        row = loop_mgr.loops.get(lid)
        if not row:
            return "hold"
        pv = loop_mgr._pv(st, row)
        sp = loop_mgr._setpoint(st, row)
        if pv is None or sp is None:
            return "hold"
        err = sp - pv
        big = float(row.get("big", 2.0))
        if abs(err) < big:
            return "hold"
        pv_needs_up = err > 0       # PV 偏低, 需要升高
        direction = int(row.get("direction", 1))
        if pv_needs_up:
            return "increase" if direction > 0 else "decrease"
        else:
            return "decrease" if direction > 0 else "increase"

    @staticmethod
    def _direction_ok(expected, current_value, action_value):
        """动作方向是否与期望一致 (✓/✗/—)"""
        if expected == "hold":
            return "—"
        try:
            av = float(action_value)
            cv = float(current_value)
        except (TypeError, ValueError):
            return "?"
        if av > cv + 0.01:
            act_dir = "increase"
        elif av < cv - 0.01:
            act_dir = "decrease"
        else:
            return "—"
        return "✓" if act_dir == expected else "✗"

    def _current_value(self, st, action):
        dev = st.devices.get(action.get("device", ""))
        if dev is None:
            return None
        try:
            return round(float(getattr(dev, action.get("param", ""), 0.0)), 2)
        except (TypeError, ValueError):
            return None

    def _load_all(self):
        out = []
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                out.append(json.loads(line))
                            except Exception:
                                continue
            except Exception:
                pass
        return out

    # ---------- 记录动作 ----------
    def _next_rid(self):
        self._seq += 1
        return uuid.uuid4().hex, self._seq

    def record_rejected(self, st, action, source="ai", loop_mgr=None,
                        reason="", review="rejected"):
        """建议被忽略/拒绝 (立即落盘, 无后续评估);
        reason: 拒绝原因 (方向错误/幅度过大/用户忽略等)
        review: 审核处置 (rejected_magnitude=幅度拦截, ignored=用户忽略)"""
        rid, seq = self._next_rid()
        rec = {"rid": rid, "seq": seq,
               "t": time.strftime("%Y-%m-%d %H:%M:%S"),
               "source": source, "outcome": "rejected",
               "device": action.get("device", ""),
               "param": action.get("param", ""),
               "value": action.get("value", ""),
               "final_value": "",
               "reason": action.get("reason", ""),
               "rejected_reason": reason,
               "review": review,
               "current_value": self._current_value(st, action),
               "expected_direction": self._expected_direction(loop_mgr, st, action),
               "direction_ok": "?",
               "before": snapshot(st)}
        self._upsert(rec)

    def record_action(self, st, action, source="manual", loop_mgr=None,
                      review="", original_value=None, before_value=None):
        """动作已执行 -> 立即落盘(pending), 60 仿真秒后评估效果并更新同一行。
        字段语义:
          value(建议值):   ai=AI原始建议值; pid=PID输出值; manual=留空
          current_value:   操作前 MV (由调用方在写入设备前抓取传入)
          final_value:     实际下发值 (翻转后可能与建议值不同)
          original_value:  仅 AI 翻转场景填 AI 原值
          review:          仅 AI 审核流程填 (adopted/flipped); manual/pid 留空"""
        cur = before_value if before_value is not None \
            else self._current_value(st, action)
        # 期望方向/方向判定只对 AI 审核流程有意义; 手动/PID 不是审核对象, 留空
        if source == "ai":
            exp = self._expected_direction(loop_mgr, st, action)
        else:
            exp = ""
        try:
            final_v = round(float(action.get("value", 0)), 2)
        except (TypeError, ValueError):
            final_v = None
        # 建议值列: AI 记原始建议, PID 记输出, 手动无建议 -> 留空
        if source == "ai":
            suggest_v = round(float(original_value), 2) \
                if original_value is not None else final_v
        elif source == "pid":
            suggest_v = final_v
        else:
            suggest_v = ""
        rid, seq = self._next_rid()
        # 方向是否正确: AI 以"原始建议值"判定 (翻转行记 ✗ 表示 AI 原始方向错);
        # manual/pid 非审核对象, 留空
        if source == "ai":
            judge_v = original_value if original_value is not None else final_v
            dir_ok = self._direction_ok(exp, cur, judge_v)
        else:
            dir_ok = ""
        rec = {"rid": rid, "seq": seq,
               "t": time.strftime("%Y-%m-%d %H:%M:%S"),
               "source": source, "outcome": "pending",
               "device": action.get("device", ""),
               "param": action.get("param", ""),
               "value": suggest_v if suggest_v != "" else "",
               "final_value": final_v if final_v is not None else "",
               "reason": action.get("reason", ""),
               "rejected_reason": "",
               "review": review,
               "original_value": (round(float(original_value), 2)
                                  if original_value is not None else ""),
               "current_value": cur,
               "expected_direction": exp,
               "direction_ok": dir_ok,
               "before": snapshot(st)}
        # 找该执行器对应回路, 用回路偏差变化评估效果
        lid = action.get("lid", "")
        self.pending.append({"rec": rec, "due": st.sim_time + EVAL_AFTER_S,
                             "lid": lid})
        self._upsert(rec)       # 执行即落盘, 文件顺序=执行顺序, 断电不丢

    # ---------- 到期评估 ----------
    def evaluate_pending(self, st, loop_mgr=None):
        if not self.pending:
            return
        remain = []
        for item in self.pending:
            if st.sim_time < item["due"]:
                remain.append(item)
                continue
            rec = item["rec"]
            after = snapshot(st)
            outcome, detail = self._judge(rec, item["lid"], st, loop_mgr)
            rec["outcome"] = outcome
            rec["after"] = after
            rec["effect"] = detail
            self._upsert(rec)        # 更新执行时已落盘的同一行 (按 rid)
        self.pending = remain

    @staticmethod
    def _loop_err(st, loop_mgr, lid):
        if loop_mgr is None:
            return None
        row = loop_mgr.loops.get(lid)
        if not row:
            return None
        pv = loop_mgr._pv(st, row)
        if pv is None:
            return None
        return abs(loop_mgr._setpoint(st, row) - pv)

    def _judge(self, rec, lid, st, loop_mgr):
        """效果判定: 相关回路偏差减小=good; 找不到回路时用全局关键偏差均分变化"""
        before = rec.get("before", {}).get("vars", {})
        after_d = snapshot(st)["vars"]
        if lid:
            e0 = self._err_from_snap(before, lid, st, loop_mgr)
            e1 = self._loop_err(st, loop_mgr, lid)
            if e0 is not None and e1 is not None:
                dlt = e1 - e0
                if dlt < -0.5:
                    return "good", f"偏差 {e0:.1f} -> {e1:.1f}"
                if dlt > 0.5:
                    return "bad", f"偏差 {e0:.1f} -> {e1:.1f}"
                return "neutral", f"偏差 {e0:.1f} -> {e1:.1f}"
        # 无回路归属(如泵启停/手动观察): 全局关键变量漂移幅度
        drift = 0.0
        n = 0
        for dev_id, field, scale in KEY_VARS:
            k = f"{dev_id}.{field}"
            if k in before and k in after_d:
                drift += abs(after_d[k] - before[k]) / scale
                n += 1
        drift = drift / max(1, n)
        if drift < 0.05:
            return "neutral", f"工况稳定(漂移{drift:.2f})"
        return "neutral", f"工况变化(漂移{drift:.2f}, 需人工判断)"

    @staticmethod
    def _err_from_snap(before_vars, lid, st, loop_mgr):
        if loop_mgr is None:
            return None
        row = loop_mgr.loops.get(lid)
        if not row:
            return None
        k = f"{row['pv_dev']}.{row['pv_field']}"
        pv = before_vars.get(k)
        if pv is None:
            return None
        sp = loop_mgr._setpoint(st, row)
        return abs(sp - pv)

    # ---------- 相似案例检索 (RAG) ----------
    def similar(self, st, k=3):
        cur = snapshot(st)
        mat = cur["material"]
        cv = cur["vars"]
        scored = []
        for rec in self._load_all():
            if rec.get("outcome") != "good":
                continue
            b = rec.get("before", {})
            if mat and b.get("material") != mat:
                continue                 # 物料体系不同不参考
            bv = b.get("vars", {})
            dist2, n = 0.0, 0
            for dev_id, field, scale in KEY_VARS:
                key = f"{dev_id}.{field}"
                if key in bv and key in cv:
                    dist2 += ((cv[key] - bv[key]) / scale) ** 2
                    n += 1
            if n >= 6:
                scored.append((math.sqrt(dist2 / n), rec))
        scored.sort(key=lambda x: x[0])
        return [r for _d, r in scored[:k]]

    # ---------- CSV 同步 ----------
    def _write_csv(self, dst):
        """把 cases.jsonl 全量写成扁平中文 CSV (Excel 友好)"""
        try:
            with open(dst, "w", encoding="utf-8-sig", newline="") as f:
                wr = csv.writer(f)
                wr.writerow(CSV_COLS)
                for rec in self._load_all():
                    b = rec.get("before", {}).get("vars", {})
                    a = rec.get("after", {}).get("vars", {})
                    wr.writerow([
                        rec.get("t", ""), rec.get("source", ""),
                        OUTCOME_CN.get(rec.get("outcome", ""),
                                       rec.get("outcome", "")),
                        rec.get("device", ""),
                        rec.get("param", ""), rec.get("value", ""),
                        rec.get("current_value", ""), rec.get("reason", ""),
                        rec.get("effect", ""), rec.get("rejected_reason", ""),
                        *[b.get(k, "") for k in _VMAP],
                        *[a.get(k, "") for k in _VMAP],
                        rec.get("expected_direction", ""),
                        rec.get("direction_ok", ""),
                        rec.get("review", ""),
                        rec.get("original_value", ""),
                        rec.get("final_value", "")])
        except Exception:
            pass

    def _sync_csv(self):
        """每次 append 后自动同步 cases.csv (与 jsonl 同目录)"""
        dst = self.path[:-6] + ".csv" if self.path.endswith(".jsonl") \
            else self.path + ".csv"
        self._write_csv(dst)

    # ---------- CSV 导出 ----------
    def export_csv(self, dst):
        self._write_csv(dst)
        return dst
