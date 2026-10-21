# -*- coding: utf-8 -*-
"""自动化实验模块 (毕业设计数据采集):
- 从 data/test_cases.json 读取 30 个预设工况, 对每个工况重复 reps 次:
    基准复位(5s) -> 注入偏差(写 PLC DB1.0/8/32 或 sim 直接设值) -> 保持 12s
    -> 调用 Ollama (真实推理, 计时) -> 方向/幅度校验 -> 记录 experiment_log.csv
    -> 保持到 30s -> 检查/复位 ESD -> 下一组
- 实验类型:
    A: Prompt 对比 (原始 vs 强化, 同一工况同一快照各调一次)
    B: 三组对比 (B1 单回路 / B2 多回路无协调 / B3 多回路有协调)
    C: 完整数据采集 (生产配置: 强化 Prompt + 全快照)
- 诚实原则: AI 未触发/无建议/格式错误/通信失败/ESD 触发 均如实记录,
  统计报告只汇总 CSV 中真实存在的行, 不补造任何数据。
- 默认观察模式: AI 建议只评估不写回 PLC (对话框可勾选"执行建议"改变)。
"""
import csv
import json
import os
import re
import struct
import sys
import threading
import time

import requests

from .ai_advisor import (
    SYS_PROMPT, SYS_PROMPT_TOP, snapshot, parse_ai_json, natural_context)
from .config import APP_DIR
from .plc import get_tags
from .case_store import CaseStore


def _bundle_dir():
    """PyInstaller onefile 模式: 打包资源解压到 sys._MEIPASS 临时目录"""
    return getattr(sys, "_MEIPASS", APP_DIR)

# 原始 Prompt (旧版, 用"回流比"术语 + 不完整机制, 用于类型 A 对比)
# 对比维度: 旧术语→新术语; 简单机制→完整决策规则
ORIGINAL_SYS_PROMPT = (
    "你是精馏装置的资深DCS工艺工程师。根据给定的设备实时状态JSON, 输出严格的JSON(不要markdown): "
    '{"analysis":"简短工况分析","actions":[{"device":"FV102","param":"opening",'
    '"value":55,"reason":"原因"}]} 。device必须是给定设备之一; param只能是 opening/speed/running/power; '
    "value为数值(opening/speed/power为0-100)。仅在需要时给出动作, 最多4条, 平稳时actions为空数组。\n\n"
    "【简单物理机制】\n"
    "- 回流比增大→塔顶温度下降\n"
    "- 回流比减小→塔顶温度上升\n"
    "- 再沸器功率增大→塔釜温度上升\n"
    "- 调整幅度≤量程10%\n"
)

BASELINE = {"temp_top": 78.0, "temp_bottom": 105.0, "level": 50.0}
# MV 复位中间值: 三个回路执行器统一复位到 50。
# 若 MV 停在 0, natural_context 会生成 "value取0以上且<0" 的矛盾指令 (模型被迫反向),
# 且翻转公式 2*mv-raw 在 mv=0 时 clamp 后失效。
MV_RESET = 50.0
MV_RESET_KEYS = (("FV104", "opening"), ("E102", "power"), ("FV106", "opening"))
RESET_WAIT = 5.0        # 注入前基准复位保持 (s)
PERSIST_WAIT = 12.0     # 注入后偏差保持时间 (s), 覆盖 hold_s=10 升级判据
TOTAL_WAIT = 30.0       # 注入后总观察时间 (s)
BIG = 2.0               # 大偏差阈值 (与回路 big 一致)
MAG_MAX = 10.0          # 单次幅度上限 (量程 0-100 的 10%)

# 注入地址: DB1 过程测量 (Real, 4 字节大端)
INJ_ADDR = {"temp_top": (1, 0), "temp_bottom": (1, 8), "level": (1, 32)}
ESD_ADDR = (4, 60)      # ESD_Trigger (Int, 2 字节)

# 三个被测回路: PV/SP/MV 与作用方向 (与 LOOP_DEFAULTS/点表一致)
LOOPS = {
    "top":    dict(lid="L3", pv_dev="T101", pv_field="temp",
                   sp_dev="T101", sp_field="sp_temp",
                   mv_dev="FV104", mv_param="opening", direction=-1),
    "bottom": dict(lid="L1", pv_dev="E102", pv_field="temp",
                   sp_dev="E102", sp_field="sp_temp",
                   mv_dev="E102", mv_param="power", direction=1),
    "level":  dict(lid="LV", pv_dev="T101", pv_field="level",
                   sp_dev="T101", sp_field="sp_level",
                   mv_dev="FV106", mv_param="opening", direction=-1),
}
# 塔釜回路备选执行器: 蒸汽阀 FV102 (加热路径, 正作用)
BOTTOM_ALT = ("FV102", "opening", 1)

CASE_FILE = os.path.join(_bundle_dir(), "data", "test_cases.json")
EXP_DIR = os.path.join(APP_DIR, "experiments")

CSV_COLS = ["timestamp", "case_id", "case_desc", "repetition",
            "experiment_type", "sub_mode", "prompt_version",
            "temp_top", "temp_bottom", "level",
            "pv_top", "pv_bottom", "pv_level",
            "sp_top", "sp_bottom", "sp_level",
            "deviation_top", "deviation_bottom", "deviation_level",
            "mv_before_top", "mv_before_bottom", "mv_before_level",
            "ai_action_top", "ai_value_top", "ai_reason_top",
            "ai_action_bottom", "ai_value_bottom", "ai_reason_bottom",
            "ai_action_level", "ai_value_level", "ai_reason_level",
            "expected_top", "expected_bottom", "expected_level",
            "direction_ok_top", "direction_ok_bottom", "direction_ok_level",
            "rejected_top", "rejected_bottom", "rejected_level",
            "injected_top", "injected_bottom", "injected_level",
            "actual_pv_top", "actual_pv_bottom", "actual_pv_level",
            "data_consistent_top", "data_consistent_bottom", "data_consistent_level",
            # 方向翻转追踪: 原始值/是否翻转/最终方向/最终正确性
            "ai_action_original_top", "ai_value_original_top",
            "ai_action_original_bottom", "ai_value_original_bottom",
            "ai_action_original_level", "ai_value_original_level",
            "ai_action_flipped_top", "ai_action_flipped_bottom",
            "ai_action_flipped_level",
            "ai_action_final_top", "ai_action_final_bottom",
            "ai_action_final_level",
            "final_ok_top", "final_ok_bottom", "final_ok_level",
            "rejected_reason", "inference_latency", "esd_triggered", "notes"]

NA = "不测"       # 该实验组不覆盖该回路
NOTRIG = "未触发"  # |偏差| <= 2.0, 不满足 AI 升级条件
NOACT = "无建议"   # 偏差超限但 AI 未对该回路给动作


def load_cases(path=CASE_FILE):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def expected_direction(direction, sp, pv, big=BIG):
    """期望的 MV 动作方向 (与 case_store._expected_direction 同规则):
    err = SP - PV; |err|<big -> hold; 否则按回路作用方向推 MV 增/减"""
    err = sp - pv
    if abs(err) < big:
        return "hold"
    pv_needs_up = err > 0
    if pv_needs_up:
        return "increase" if direction > 0 else "decrease"
    return "decrease" if direction > 0 else "increase"


def _dir_ok(expected, cur, val):
    """动作方向是否正确 (✓/✗/—), 与 case_store._direction_ok 同规则"""
    if expected == "hold" or cur is None or val is None:
        return "—"
    if val > cur + 0.01:
        return "✓" if expected == "increase" else "✗"
    if val < cur - 0.01:
        return "✓" if expected == "decrease" else "✗"
    return "—"


class ExperimentRunner(threading.Thread):
    """实验运行线程 (与界面解耦: 通过 on_* 回调上报; Qt 侧用 Bridge 转信号)"""

    def __init__(self, cfg, st, cases, exp_type="C", reps=1, sub_modes=None,
                 exec_suggestions=False, log_file=None, summary_file=None,
                 own_poll=False, esd_reset_hook=None,
                 case_store=None, rag=True, compare=False,
                 on_progress=None, on_step=None, on_done=None):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.st = st
        self.cases = cases
        self.exp_type = exp_type          # A / B / C
        self.reps = max(1, int(reps))
        self.sub_modes = sub_modes        # 类型 B 的分组列表 (None=全部三组)
        self.exec_suggestions = bool(exec_suggestions)
        # RAG 相似案例注入:
        #   case_store: 案例库实例 (None=空库对照, 不注入任何历史案例)
        #   rag: 是否启用注入开关 (即使有库也可临时关闭, 便于对照)
        #   compare: 学习对比模式 —— 自动跑两遍 (空库 baseline + 种子库 seed),
        #            各自生成独立 CSV/summary, 最后输出对照报告
        self.case_store = case_store
        self.rag = bool(rag) and case_store is not None
        self.compare = bool(compare)
        # 对比模式下的种子库 (从 data/seed_cases.jsonl 加载, 与日常库隔离)
        self._seed_cs = None
        if self.compare:
            seed_path = os.path.join(_bundle_dir(), "data", "seed_cases.jsonl")
            if os.path.exists(seed_path):
                self._seed_cs = CaseStore(path=seed_path)
        self._phase_stats = []     # 各 phase 的统计结果, 用于对照报告
        os.makedirs(EXP_DIR, exist_ok=True)
        # 每次启动用带时间戳的新文件, 避免旧表头不匹配导致列错位
        if log_file is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            self.log_file = os.path.join(EXP_DIR, f"experiment_log_{ts}.csv")
            self.summary_file = os.path.join(EXP_DIR, f"summary_{ts}.md")
        else:
            self.log_file = log_file
            self.summary_file = summary_file or os.path.join(EXP_DIR, "summary.md")
        self.own_poll = own_poll          # 无界面轮询 (headless) 时自行读 PLC
        self.esd_reset_hook = esd_reset_hook
        self.on_progress = on_progress    # fn(ci, total, rep, reps, msg)
        self.on_step = on_step            # fn(text)
        self.on_done = on_done            # fn(summary_path or "")
        self._stop = False
        self._paused = False
        self.rows = []                    # 本次已记录的全部行 (报告用)
        self._client = None               # snap7 client (PLC 模式)
        self._conn_id = "—"               # 本次连接ID (日志追踪用)
        self._conn_seq = 0                # 重连序号
        self._tags = get_tags(cfg)
        self._tag_map = {(t["dev"], t["field"]): t for t in self._tags}
        self.model = cfg.get("ai_model", "")
        self.base_url = cfg.get("ollama_url", "")

    # ---------- 控制接口 ----------
    def pause(self, on=True):
        self._paused = bool(on)

    def stop(self):
        self._stop = True

    def _ck(self):
        """暂停/停止检查; 返回 False 表示需要中止"""
        while self._paused and not self._stop:
            time.sleep(0.2)
        return not self._stop

    def _wait(self, seconds, step=""):
        """可中断等待; 期间自行轮询 PLC (headless)"""
        end = time.time() + seconds
        while time.time() < end:
            if not self._ck():
                return False
            if self.own_poll and self._client is not None:
                self._poll_once()
            time.sleep(0.2)
        return not self._stop

    def _emit_step(self, text):
        if self.on_step:
            try:
                self.on_step(text)
            except Exception:
                pass

    def _emit_progress(self, ci, total, rep, msg=""):
        if self.on_progress:
            try:
                self.on_progress(ci, total, rep, self.reps, msg)
            except Exception:
                pass

    # ---------- PLC I/O ----------
    def _conn_log(self, msg):
        """连接生命周期日志: logs/plc_connection.log (时刻 + 连接ID)"""
        try:
            log_dir = os.path.join(APP_DIR, "logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "plc_connection.log"),
                      "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"[exp-thread][{self._conn_id}] {msg}\n")
        except Exception:
            pass

    def _verify_conn(self):
        """连接可用性验证: 读 DB1.0/8/32 三个 REAL, 全部合法才算通过"""
        for db, off in ((1, 0), (1, 8), (1, 32)):
            try:
                raw = self._client.db_read(db, off, 4)
                v = struct.unpack(">f", bytes(raw))[0]
            except Exception as e:
                self._conn_log(f"读验证失败 DB{db}.{off}: {e}")
                return False
            if v != v or not (-1000.0 < v < 10000.0):
                self._conn_log(f"读验证值非法 DB{db}.{off}={v}")
                return False
        self._conn_log("读验证通过 (DB1.0/8/32 均可读)")
        return True

    def _connect(self):
        if self.st.mode != "plc":
            return True
        # 已有连接且读验证通过则直接复用 (headless 预检/run 可能重复调用)
        if self._client is not None:
            try:
                if self._verify_conn():
                    return True
            except Exception:
                pass
            self._drop_client()
        try:
            import snap7
            p = self.cfg["plc"]
            c = snap7.client.Client()
            self._conn_seq += 1
            self._conn_id = (f"exp-{time.strftime('%H%M%S')}-"
                             f"{self._conn_seq}-{threading.get_ident() % 100000}")
            self._conn_log(f"连接中 host={p['host']} rack={p.get('rack',0)} "
                           f"slot={p.get('slot',1)}")
            c.connect(p["host"], int(p.get("rack", 0)), int(p.get("slot", 1)),
                      tcp_port=int(p.get("s7_port", 102)))
            if not c.get_connected():
                raise IOError("connect failed")
            self._client = c
            self._read_fails = 0
            if not self._verify_conn():
                self._drop_client()
                return False
            self._conn_log("连接成功")
            return True
        except Exception as e:
            self._conn_log(f"连接失败: {e}")
            self._emit_step(f"PLC 连接失败: {e}")
            return False

    def _drop_client(self):
        """关闭并销毁当前 client"""
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            try:
                self._client.destroy()
            except Exception:
                pass
        self._client = None

    def _reconnect(self):
        """连接丢失后重连: 释放旧连接 -> 新建 -> 读验证通过才算成功"""
        self._emit_step("PLC 连接丢失, 尝试重连...")
        self._conn_log("连接丢失, 开始重连")
        self._drop_client()
        ok = self._connect()   # _connect 内部分配新 conn_id 并做读验证
        if ok:
            self._conn_log("重连成功, 继续实验")
            self._emit_step("PLC 重连成功, 继续实验")
        else:
            self._conn_log("重连失败")
        return ok

    def _poll_once(self):
        """读全部只读点 -> 更新本地设备状态 (headless 模式用);
        读失败不再静默: 连续失败 >=3 时重连一次"""
        for t in self._tags:
            if "R" not in t.get("rw", "R").upper():
                continue
            size = 4 if t.get("dtype", "real") == "real" else 2
            try:
                raw = self._client.db_read(int(t["db"]), int(t["off"]), size)
            except Exception:
                self._read_fails = getattr(self, "_read_fails", 0) + 1
                if self._read_fails >= 3:
                    self._read_fails = 0
                    if not self._reconnect():
                        return   # 重连失败, 下轮再试
                return
            self._read_fails = 0
            if t.get("dtype", "real") == "real":
                x = struct.unpack(">f", bytes(raw))[0]
            else:
                x = float(struct.unpack(">h", bytes(raw))[0])
            v = x * float(t.get("scale", 1.0)) + float(t.get("offset", 0.0))
            if v != v:
                continue
            dev = self.st.devices.get(t["dev"])
            if dev is not None and hasattr(dev, t["field"]):
                setattr(dev, t["field"], float(v))

    def _write_raw(self, db, off, dtype, value):
        """绕过点表读写标志的原始写 (注入 PV / ESD 复位 / 执行建议)"""
        if self._client is None:
            return False
        try:
            if dtype == "real":
                payload = struct.pack(">f", float(value))
            else:
                payload = struct.pack(">h", int(round(float(value))))
            self._client.db_write(int(db), int(off), payload)
            return True
        except Exception as e:
            self._emit_step(f"PLC 写入失败 DB{db}.{off}: {e}")
            return False

    def _inject(self, case, timeout=10.0):
        """注入工况: PLC 写 DB1.0/8/32, 轮询等待回读值接近注入值(±0.5);
        写失败自动重连重试(最多3次); 超过 timeout 仍不达标则放弃(返回 ✗)。
        返回 dict: {lid: (injected, actual, ok)}"""
        injected = {"top": case["temp_top"], "bottom": case["temp_bottom"],
                    "level": case["level"]}
        result = {}
        if self.st.mode == "plc":
            key_map = {"top": ("T101", "temp"),
                       "bottom": ("E102", "temp"),
                       "level": ("T101", "level")}
            deadline = time.time() + timeout
            attempt = 0
            while True:
                attempt += 1
                # 1) 写 PLC (3 个点全部成功才算写成功)
                w_ok = True
                for key, (db, off) in INJ_ADDR.items():
                    if not self._write_raw(db, off, "real", case[key]):
                        w_ok = False
                if not w_ok:
                    if attempt >= 3 or not self._reconnect():
                        break
                    continue
                # 2) 轮询本回合 (最多4s), 每300ms读一次, 连续2次±0.5内算稳
                t0 = time.time()
                stable = 0
                last_vals = {}
                while time.time() - t0 < 4.0:
                    self._poll_once()
                    cur = {lid: float(getattr(self.st.devices[dev], field))
                           for lid, (dev, field) in key_map.items()}
                    ok_all = all(abs(cur[lid] - injected[lid]) <= 0.5
                                 for lid in cur)
                    if ok_all and last_vals and all(
                            abs(cur[lid] - last_vals[lid]) < 0.05
                            for lid in cur):
                        stable += 1
                    else:
                        stable = 0
                    last_vals = cur
                    if stable >= 2:
                        break
                    time.sleep(0.3)
                # 3) 达标 → 结束; 未达标且没超时 → 重写再试; 超时 → 放弃
                if last_vals and all(
                        abs(last_vals[lid] - injected[lid]) <= 0.5
                        for lid in last_vals):
                    break
                if time.time() >= deadline or attempt >= 3:
                    break
            # 4) 最终回读, 生成结果 (可能未达标 → ✗)
            self._poll_once()
            for lid, (dev, field) in key_map.items():
                v = float(getattr(self.st.devices[dev], field))
                result[lid] = (injected[lid], v,
                               "✓" if abs(v - injected[lid]) <= 0.5 else "✗")
        else:
            # sim 模式: 直接设值, 无 PLC 回读问题
            self.st.devices["T101"].temp = float(case["temp_top"])
            self.st.devices["E102"].temp = float(case["temp_bottom"])
            self.st.devices["T101"].level = float(case["level"])
            result = {lid: (injected[lid], injected[lid], "✓")
                      for lid in injected}
        return result

    def _reset_baseline(self):
        """复位到基准工况: PV 写基准值; MV 统一复位到 50 (中间值)"""
        self._inject({"temp_top": BASELINE["temp_top"],
                      "temp_bottom": BASELINE["temp_bottom"],
                      "level": BASELINE["level"]})
        if self.st.mode == "plc":
            for dev, field in MV_RESET_KEYS:
                t = self._tag_map.get((dev, field))
                if not t:
                    continue
                ok = self._write_raw(t["db"], t["off"],
                                     t.get("dtype", "real"), MV_RESET)
                if not ok:
                    # 写失败重连一次再试 (连接丢失时不让 MV 停在旧值)
                    self._conn_log(f"复位写 MV {dev}.{field} 失败, 重连重试")
                    if self._reconnect():
                        self._write_raw(t["db"], t["off"],
                                        t.get("dtype", "real"), MV_RESET)
        # 本地状态同步 (sim 模式/写后立即生效, 不等下轮轮询)
        for dev, field in MV_RESET_KEYS:
            dv = self.st.devices.get(dev)
            if dv is not None and hasattr(dv, field):
                setattr(dv, field, MV_RESET)

    def _read_esd(self):
        """读 ESD_Trigger 原始值 (PLC 模式); sim 模式看本地标志"""
        if self.st.mode != "plc" or self._client is None:
            return 2 if self.st.esd_locked else 0
        t = self._tag_map.get(("ESD", "trigger"))
        if not t:
            return 0
        try:
            raw = self._client.db_read(int(t["db"]), int(t["off"]), 2)
            return int(struct.unpack(">h", bytes(raw))[0])
        except Exception:
            return 0

    def _esd_reset(self):
        """复位 ESD: 写 0 + 清本地标志"""
        if self.st.mode == "plc":
            self._write_raw(ESD_ADDR[0], ESD_ADDR[1], "int", 0)
            if self.esd_reset_hook:
                try:
                    self.esd_reset_hook()
                except Exception:
                    pass
        self.st.esd_locked = False
        self.st.esd_reason = ""
        self.st.esd_trigger_val = 0
        self.st.esd_plc_cleared = False
        time.sleep(0.5)

    # ---------- AI 调用 ----------
    def _call_ai(self, system, user_msg):
        """同步调用 Ollama /api/chat (与生产 payload 一致); 返回 (parsed, latency_ms, err)"""
        t0 = time.time()
        try:
            r = requests.post(
                self.base_url + "/api/chat", timeout=60,
                json={"model": self.model, "stream": False,
                      # temperature=0 保证可复现, 便于学习前后对比实验排除随机噪声
                      "options": {"temperature": 0.0},
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user_msg}]})
            raw = r.json().get("message", {}).get("content", "")
        except Exception as e:
            return None, -1, f"通信失败: {e}"
        latency = int((time.time() - t0) * 1000)
        # 实验调试日志: 每次调用的 Prompt 摘要 + 原始响应
        try:
            with open(os.path.join(APP_DIR, "logs", "experiment_ai_debug.log"),
                      "a", encoding="utf-8") as f:
                f.write(f"\n{'='*70}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"model={self.model} latency={latency}ms\n"
                        f"--- SYS({len(system)}B) ---\n{system[:400]}...\n"
                        f"--- USER ---\n{user_msg[:600]}\n"
                        f"--- RAW ---\n{raw}\n")
        except Exception:
            pass
        parsed = parse_ai_json(raw)
        if parsed is None:
            return None, latency, "格式错误(无法解析JSON)"
        return parsed, latency, ""

    # ---------- 校验与行构建 ----------
    def _loop_state(self, key):
        L = LOOPS[key]
        d = self.st.devices
        pv = float(getattr(d[L["pv_dev"]], L["pv_field"]))
        sp_v = getattr(d[L["sp_dev"]], L["sp_field"], None)
        sp = float(sp_v) if sp_v is not None else BASELINE.get(
            "level" if key == "level" else
            ("temp_top" if key == "top" else "temp_bottom"))
        mv = float(getattr(d[L["mv_dev"]], L["mv_param"]))
        return pv, sp, mv

    def _map_action(self, key, actions):
        """从 AI 动作列表中找该回路执行器的动作"""
        for a in actions:
            dev, param = a.get("device", ""), a.get("param", "")
            if key == "top" and dev == "FV104" and param == "opening":
                return a, ("FV104", "opening", LOOPS["top"]["direction"])
            if key == "bottom":
                if dev == "E102" and param == "power":
                    return a, ("E102", "power", LOOPS["bottom"]["direction"])
                if dev == "FV102" and param == "opening":
                    return a, BOTTOM_ALT
            if key == "level" and dev == "FV106" and param == "opening":
                return a, ("FV106", "opening", LOOPS["level"]["direction"])
        return None, None

    @staticmethod
    def _dir_label(cur, val):
        """相对当前值的方向标签"""
        if val > cur + 0.01:
            return "increase"
        if val < cur - 0.01:
            return "decrease"
        return "hold"

    def _eval_loop(self, key, actions, cell, notes):
        """评估单个回路 (翻转策略):
        - direction_ok_* 记录 AI 原始方向是否正确 (体现 AI 能力)
        - 方向错误 → 翻转方向保留幅度; 幅度过大 → 截断到 ±10; 范围 → clamp 0-100
        - final_ok_* 记录最终下发方向是否正确 (体现系统安全能力, 翻转后应恒为 ✓)
        """
        pv, sp, mv = self._loop_state(key)
        cell[f"pv_{key}"], cell[f"sp_{key}"] = round(pv, 2), round(sp, 2)
        cell[f"deviation_{key}"] = round(sp - pv, 2)
        cell[f"mv_before_{key}"] = round(mv, 2)
        exp = expected_direction(LOOPS[key]["direction"], sp, pv)
        cell[f"expected_{key}"] = exp
        act, mvdef = self._map_action(key, actions)
        # 无需动作的工况
        if abs(sp - pv) < BIG and act is None:
            for c in (f"ai_action_{key}", f"ai_action_original_{key}",
                      f"ai_action_final_{key}"):
                cell[c] = NOTRIG
            cell[f"ai_value_{key}"] = cell[f"ai_value_original_{key}"] = ""
            cell[f"ai_reason_{key}"] = ""
            for c in (f"direction_ok_{key}", f"rejected_{key}",
                      f"ai_action_flipped_{key}", f"final_ok_{key}"):
                cell[c] = "—"
            return
        if act is None:
            for c in (f"ai_action_{key}", f"ai_action_original_{key}",
                      f"ai_action_final_{key}"):
                cell[c] = NOACT
            cell[f"ai_value_{key}"] = cell[f"ai_value_original_{key}"] = ""
            cell[f"ai_reason_{key}"] = ""
            for c in (f"direction_ok_{key}", f"rejected_{key}",
                      f"ai_action_flipped_{key}", f"final_ok_{key}"):
                cell[c] = "—"
            return
        # ---- AI 原始建议 ----
        raw_val = float(act.get("value", 0))
        raw_dir = self._dir_label(mv, raw_val)
        raw_ok = _dir_ok(exp, mv, raw_val)
        flipped = False
        # ---- 安全层: 方向翻转 (保留幅度) ----
        final_val = raw_val
        if exp != "hold" and raw_ok == "✗":
            final_val = 2.0 * mv - raw_val      # 以当前值为镜相反转
            flipped = True
        # ---- 安全层: 幅度截断 (单次 ≤10) ----
        mag_clamped = False
        if abs(final_val - mv) > MAG_MAX + 0.01:
            final_val = mv + (MAG_MAX if final_val > mv else -MAG_MAX)
            mag_clamped = True
        # ---- 范围 clamp 0-100 ----
        final_val = max(0.0, min(100.0, final_val))
        final_dir = self._dir_label(mv, final_val)
        final_ok = _dir_ok(exp, mv, final_val)
        # ---- 写单元格 ----
        act_label = f"{act.get('device','')}.{act.get('param','')}="
        cell[f"ai_action_original_{key}"] = act_label + raw_dir
        cell[f"ai_value_original_{key}"] = raw_val
        cell[f"ai_action_flipped_{key}"] = "✓" if flipped else "✗"
        cell[f"ai_action_final_{key}"] = act_label + final_dir
        cell[f"final_ok_{key}"] = final_ok
        # 兼容旧列: ai_action/ai_value 表示最终下发值
        cell[f"ai_action_{key}"] = act_label + final_dir
        cell[f"ai_value_{key}"] = round(final_val, 1)
        cell[f"ai_reason_{key}"] = str(act.get("reason", ""))[:200]
        cell[f"direction_ok_{key}"] = raw_ok
        cell[f"rejected_{key}"] = "否"     # 翻转策略下不拦截, 只修正
        if flipped:
            notes.append(f"{key}:方向翻转({raw_dir}→{final_dir})")
        if mag_clamped:
            notes.append(f"{key}:幅度截断")
        # ---- 执行建议 (可选): 写回的是翻转/截断后的安全值 ----
        if self.exec_suggestions and self.st.mode == "plc":
            t = self._tag_map.get(mvdef[0:2])
            if t and "W" in t.get("rw", "R").upper():
                self._write_raw(t["db"], t["off"], t.get("dtype", "real"),
                                final_val)
                dev = self.st.devices.get(mvdef[0])
                if dev is not None:
                    setattr(dev, mvdef[1], final_val)

    def _new_row(self, case, rep, sub_mode, prompt_version, latency, notes,
                 esd, inj_result=None, skip_loops=()):
        row = {c: "" for c in CSV_COLS}
        row.update({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "case_id": case["id"], "case_desc": case.get("desc", ""),
            "repetition": rep, "experiment_type": self.exp_type,
            "sub_mode": sub_mode, "prompt_version": prompt_version,
            "temp_top": case["temp_top"], "temp_bottom": case["temp_bottom"],
            "level": case["level"],
            "inference_latency": latency, "esd_triggered": esd,
            "rejected_reason": ";".join(notes),
            "notes": ";".join(notes)})
        # 注入/回读/一致性字段
        lid_map = {"top": "temp_top", "bottom": "temp_bottom", "level": "level"}
        if inj_result:
            for lid, col in lid_map.items():
                inj, actual, ok = inj_result.get(lid, (case.get(col, ""), "", ""))
                row[f"injected_{lid}"] = round(float(inj), 2)
                row[f"actual_pv_{lid}"] = round(float(actual), 2) if actual != "" else ""
                row[f"data_consistent_{lid}"] = ok
        for key in ("top", "bottom", "level"):
            if key in skip_loops:
                for c in (f"ai_action_{key}", f"ai_action_original_{key}",
                          f"ai_action_final_{key}"):
                    row[c] = NA
                for c in (f"expected_{key}", f"direction_ok_{key}",
                          f"rejected_{key}", f"ai_action_flipped_{key}",
                          f"final_ok_{key}"):
                    row[c] = "—"
        return row

    def _write_row(self, row):
        self.rows.append(row)
        new = not os.path.exists(self.log_file)
        try:
            with open(self.log_file, "a", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=CSV_COLS)
                if new:
                    w.writeheader()
                w.writerow(row)
        except Exception as e:
            self._emit_step(f"CSV 写入失败: {e}")

    # ---------- 主流程 ----------
    def _rag_hint(self):
        """检索同物料相似好案例, 拼写成历史参考段 (复用生产侧格式)。
        RAG 关闭或无匹配 good 案例时返回空串, 不影响原 Prompt。"""
        if not self.rag or self.case_store is None:
            return ""
        try:
            cases = self.case_store.similar(self.st, k=3)
        except Exception:
            return ""
        if not cases:
            return ""
        lines = ["\n\n【历史相似工况参考 — 同物料, 人工确认的正确操作, 仅供参考, 不必照抄】"]
        for i, c in enumerate(cases, 1):
            bv = c.get("before", {}).get("vars", {})
            compact = ", ".join(f"{k}={v:g}"
                                for k, v in list(bv.items())[:8])
            lines.append(
                f"{i}. 当时工况: {compact}; 正确操作: {c.get('device','')}."
                f"{c.get('param','')}={c.get('value','')} "
                f"({c.get('reason','')})")
        return "\n".join(lines)

    def _call_plan(self, case):
        """按实验类型生成调用计划: [(sub_mode, prompt_version, system, user_msg)]
        - 原始Prompt(A组基线): 旧术语 + 纯JSON (模型需自己判断符号)
        - 强化Prompt: 自然语言工况指令(已给出偏差与调节方向) + JSON参考
          + (RAG开启时) 历史相似好案例参考"""
        snap_full = json.dumps(snapshot(self.st), ensure_ascii=False)
        nat_full = natural_context(self.st, ("top", "bottom", "level"))
        hint = self._rag_hint()
        strong_full = nat_full + "\n\n【实时数据JSON(参考)】\n" + snap_full + hint
        plans = []
        if self.exp_type == "A":
            plans.append(("全回路", "原始", ORIGINAL_SYS_PROMPT, snap_full))
            plans.append(("全回路", "强化", SYS_PROMPT, strong_full))
        elif self.exp_type == "C":
            plans.append(("全回路", "强化", SYS_PROMPT, strong_full))
        else:  # B
            modes = self.sub_modes or ["B1单回路", "B2多回路无协调", "B3多回路有协调"]
            if "B1单回路" in modes:
                nat_top = natural_context(self.st, ("top",))
                snap_top = json.dumps(snapshot(self.st, "T101"), ensure_ascii=False)
                plans.append(("B1单回路", "强化", SYS_PROMPT_TOP,
                              nat_top + "\n\n【实时数据JSON(参考)】\n" + snap_top
                              + hint))
            if "B2多回路无协调" in modes:
                plans.append(("B2多回路无协调", "强化", SYS_PROMPT, strong_full))
            if "B3多回路有协调" in modes:
                coord = ("\n\n【多回路协调】当前为多回路耦合工况, 请统一考虑塔顶温度/塔釜温度/"
                         "塔釜液位三个回路的相互影响, 给出协调一致、互不冲突的动作组合; "
                         "某回路无需动作时不要硬给动作。")
                plans.append(("B3多回路有协调", "强化", SYS_PROMPT,
                              strong_full + coord))
        return plans

    def _run_case(self, case, ci, total, rep):
        # 1) 基准复位 + 5s
        self._emit_progress(ci, total, rep, "基准复位")
        self._reset_baseline()
        if not self._wait(RESET_WAIT, "基准复位保持"):
            return
        # 2) 注入 + 保持 12s
        self._emit_progress(ci, total, rep, f"注入工况: {case.get('desc','')}")
        inj_result = self._inject(case)   # {lid: (injected, actual, ok)}
        # 数据一致性检查: 任一回路 ✗ → 记"注入失败", 跳过该工况 (不浪费 AI 调用)
        bad = [f"{k}注入={inj_result[k][0]} 回读={round(inj_result[k][1],2)}"
               for k in inj_result if inj_result[k][2] == "✗"]
        if bad:
            self._emit_step(
                f"⚠ 工况{case['id']}: 注入失败 → {', '.join(bad)}, 跳过本工况")
            pver = ("原始" if self.exp_type == "A" else
                    "强化" if self.exp_type == "C" else "强化")
            row = self._new_row(case, rep, f"{self.exp_type}-跳过", pver,
                                -1, [], 0, inj_result=inj_result)
            for key in ("top", "bottom", "level"):
                pv, sp, mv = self._loop_state(key)
                row[f"pv_{key}"] = round(pv, 2)
                row[f"sp_{key}"] = round(sp, 2)
                row[f"deviation_{key}"] = round(sp - pv, 2)
                row[f"mv_before_{key}"] = round(mv, 2)
                row[f"expected_{key}"] = expected_direction(
                    LOOPS[key]["direction"], sp, pv)
                row[f"ai_action_{key}"] = "未注入"
                row[f"ai_action_original_{key}"] = "未注入"
                row[f"ai_action_final_{key}"] = "未注入"
                row[f"ai_value_{key}"] = row[f"ai_value_original_{key}"] = ""
                row[f"ai_reason_{key}"] = ""
                row[f"direction_ok_{key}"] = "—"
                row[f"rejected_{key}"] = "—"
                row[f"ai_action_flipped_{key}"] = "—"
                row[f"final_ok_{key}"] = "—"
            row["rejected_reason"] = "注入失败"
            row["notes"] = f"注入失败: {', '.join(bad)}"
            row["inference_latency"] = ""
            self._write_row(row)
            return
        t_inj = time.time()
        if not self._wait(PERSIST_WAIT, "偏差保持(10s升级判据)"):
            return
        # 3) ESD 预检 (极端工况可能已触发硬联锁)
        esd = 0
        if self._read_esd() != 0:
            esd = 1
            self._emit_step(f"工况{case['id']}: ESD 联锁触发, 自动复位后继续")
            self._esd_reset()
        # 4) AI 调用计划
        for sub_mode, pver, system, user_msg in self._call_plan(case):
            if not self._ck():
                return
            self._emit_progress(ci, total, rep, f"AI 推理: {sub_mode}/{pver}")
            parsed, latency, err = self._call_ai(system, user_msg)
            row = self._new_row(case, rep, sub_mode, pver, latency, [],
                                esd, inj_result=inj_result,
                                skip_loops=("bottom", "level")
                                if sub_mode == "B1单回路" else ())
            if parsed is None:
                # 通信失败 / 格式错误: 填充真实偏差, 如实标记各回路状态
                tag = "通信失败" if err.startswith("通信失败") else "格式错误"
                for key in ("top", "bottom", "level"):
                    if row.get(f"ai_action_{key}") == NA:
                        continue
                    pv, sp, mv = self._loop_state(key)
                    row[f"pv_{key}"] = round(pv, 2)
                    row[f"sp_{key}"] = round(sp, 2)
                    row[f"deviation_{key}"] = round(sp - pv, 2)
                    row[f"mv_before_{key}"] = round(mv, 2)
                    row[f"expected_{key}"] = expected_direction(
                        LOOPS[key]["direction"], sp, pv)
                    label = tag if abs(sp - pv) >= BIG else NOTRIG
                    row[f"ai_action_{key}"] = label
                    row[f"ai_action_original_{key}"] = label
                    row[f"ai_action_final_{key}"] = label
                    row[f"ai_value_{key}"] = row[f"ai_value_original_{key}"] = ""
                    row[f"ai_reason_{key}"] = ""
                    row[f"direction_ok_{key}"] = "—"
                    row[f"rejected_{key}"] = "—"
                    row[f"ai_action_flipped_{key}"] = "—"
                    row[f"final_ok_{key}"] = "—"
                row["notes"] = tag
                row["rejected_reason"] = tag
                self._write_row(row)
                continue
            actions = parsed.get("actions", [])
            notes = []
            for key in ("top", "bottom", "level"):
                if row.get(f"ai_action_{key}") == NA:
                    continue
                self._eval_loop(key, actions, row, notes)
            row["rejected_reason"] = ";".join(notes)
            row["notes"] = ";".join(notes) if notes else ""
            self._write_row(row)
        # 5) 保持到注入后 30s
        remain = TOTAL_WAIT - (time.time() - t_inj)
        if remain > 0 and not self._wait(remain, "观察保持"):
            return
        # 6) ESD 后检
        if self._read_esd() != 0:
            self._esd_reset()

    def run(self):
        ok = self._connect()
        total = len(self.cases)
        if not ok and self.st.mode == "plc":
            for cb in (self.on_done,):
                if cb:
                    cb("")
            return
        # 对比模式跑两遍: baseline(空库) -> seed(种子库); 普通模式只跑一遍
        if self.compare:
            phases = [("baseline", None),
                      ("seed", self._seed_cs)]
        else:
            phases = [("main", self.case_store)]
        ts = time.strftime("%Y%m%d_%H%M%S")
        try:
            for ph_name, ph_cs in phases:
                if self._stop:
                    break
                # 切换本 phase 的案例库与 rag 状态
                self.case_store = ph_cs
                self.rag = ph_cs is not None
                # 本 phase 独立的输出文件 (带类型/模式/phase 后缀, 多轮数据严格分开)
                mode_tag = "_selftest" if self.st.mode == "sim" else ""
                suffix = f"_{ph_name}" if self.compare else ""
                stamp = f"experiment_log_{ts}_{self.exp_type}{mode_tag}{suffix}"
                self.log_file = os.path.join(EXP_DIR, stamp + ".csv")
                self.summary_file = os.path.join(
                    EXP_DIR, stamp.replace("experiment_log", "summary") + ".md")
                self.rows = []
                self._emit_step(f"==== 学习对比 Phase: {ph_name} "
                                f"(案例库={'空库' if ph_cs is None else '种子库'}) ====")
                for ci, case in enumerate(self.cases, 1):
                    if self._stop:
                        break
                    for rep in range(1, self.reps + 1):
                        if self._stop:
                            break
                        self._run_case(case, ci, total, rep)
                # 本 phase 结束: 写 summary, 收集统计
                if self.rows:
                    stats = self._write_summary()
                    self._phase_stats.append((ph_name, stats))
        finally:
            # 无论正常结束/停止/异常, 都释放实验连接 (主轮询由对话框恢复)
            if self.st.mode == "plc":
                self._conn_log("实验结束, 断开连接")
                self._drop_client()
        # 对比模式: 写对照报告
        out_path = ""
        if self.compare and len(self._phase_stats) == 2:
            out_path = self._write_compare_report(ts)
        elif self._phase_stats:
            out_path = self._phase_stats[0][1].get("summary_path", "")
        if self.on_done:
            try:
                self.on_done(out_path)
            except Exception:
                pass

    # ---------- 报告 ----------
    @staticmethod
    def _rate(rows, key):
        """AI 原始方向正确率: ✓ / (✓+✗), 忽略 —/不测"""
        ok = sum(1 for r in rows if r.get(f"direction_ok_{key}") == "✓")
        bad = sum(1 for r in rows if r.get(f"direction_ok_{key}") == "✗")
        return ok, bad, (100.0 * ok / (ok + bad)) if (ok + bad) else None

    @staticmethod
    def _final_rate(rows, key):
        """翻转后最终下发方向正确率: final_ok ✓ / (✓+✗)"""
        ok = sum(1 for r in rows if r.get(f"final_ok_{key}") == "✓")
        bad = sum(1 for r in rows if r.get(f"final_ok_{key}") == "✗")
        return ok, bad, (100.0 * ok / (ok + bad)) if (ok + bad) else None

    def _write_summary(self):
        rows = self.rows
        L = []
        L.append(f"# 自动实验报告 summary\n")
        L.append(f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        L.append(f"- 模型: {self.model}  |  Ollama: {self.base_url}")
        L.append(f"- 实验类型: {self.exp_type}  |  重复次数/工况: {self.reps}")
        L.append(f"- 工况文件: data/test_cases.json ({total_cases()} 组)")
        L.append(f"- 模式: {'PLC(真实注入)' if self.st.mode == 'plc' else 'sim(直接设值, 自测)'}"
                 f"  |  AI建议执行: {'是' if self.exec_suggestions else '否(观察模式)'}")
        L.append(f"- 日志: {os.path.basename(self.log_file)} ({len(rows)} 行)\n")

        # 1 实验概况
        L.append("## 1. 实验概况\n")
        L.append(f"- 总行数(建议记录): {len(rows)}")
        types = {}
        for r in rows:
            k = f"{r['experiment_type']}/{r.get('sub_mode','')}/{r.get('prompt_version','')}"
            types[k] = types.get(k, 0) + 1
        for k, v in sorted(types.items()):
            L.append(f"  - {k}: {v} 行")
        L.append("")

        # 2 注入成功率 (数据有效性)
        inj_fail = sum(1 for r in rows
                       if r.get("rejected_reason") == "注入失败"
                       or "注入失败" in (r.get("notes", "") or ""))
        L.append("## 2. 注入成功率 (数据有效性)\n")
        L.append(f"- 注入成功: {len(rows) - inj_fail}/{len(rows)} 行")
        if inj_fail:
            L.append(f"- ⚠ 注入失败(已跳过AI调用, 数据如实保留): {inj_fail} 行")
        L.append("")

        # 3 方向正确率 (AI原始 + 翻转后最终)
        L.append("## 3. 方向正确率 (仅统计偏差>2.0°C且AI给出动作的行)\n")
        L.append("| 回路 | AI原始正确 | AI原始正确率 | 翻转次数 | "
                 "最终下发正确 | 最终正确率 |")
        L.append("|---|---|---|---|---|---|")
        sum_raw_ok = sum_raw_bad = sum_fin_ok = sum_fin_bad = 0
        for key, cn in (("top", "塔顶"), ("bottom", "塔釜"), ("level", "液位")):
            rok, rbad, rrate = self._rate(rows, key)
            fok, fbad, frate = self._final_rate(rows, key)
            flips = sum(1 for r in rows
                        if r.get(f"ai_action_flipped_{key}") == "✓")
            sum_raw_ok += rok; sum_raw_bad += rbad
            sum_fin_ok += fok; sum_fin_bad += fbad
            rs = f"{rrate:.1f}%" if rrate is not None else "N/A"
            fs = f"{frate:.1f}%" if frate is not None else "N/A"
            L.append(f"| {cn} | {rok}/{rok+rbad} | {rs} | {flips} | "
                     f"{fok}/{fok+fbad} | {fs} |")
        rall = (100.0 * sum_raw_ok / (sum_raw_ok + sum_raw_bad)
                if (sum_raw_ok + sum_raw_bad) else None)
        fall = (100.0 * sum_fin_ok / (sum_fin_ok + sum_fin_bad)
                if (sum_fin_ok + sum_fin_bad) else None)
        L.append(f"| **总体** | **{sum_raw_ok}/{sum_raw_ok+sum_raw_bad}** | "
                 f"**{f'{rall:.1f}%' if rall is not None else 'N/A'}** | "
                 f"{sum(1 for r in rows for k in ('top','bottom','level') if r.get(f'ai_action_flipped_{k}')=='✓')} | "
                 f"**{sum_fin_ok}/{sum_fin_ok+sum_fin_bad}** | "
                 f"**{f'{fall:.1f}%' if fall is not None else 'N/A'}** |")
        L.append("")
        L.append("> 说明: AI原始正确率体现大模型自身能力; "
                 "最终正确率体现安全层(方向翻转+幅度截断+范围clamp)保障后的下发质量。\n")

        # 4 安全层统计 (翻转/截断, 翻转策略下不拦截)
        L.append("## 4. 安全层统计 (翻转策略)\n")
        sug = sum(1 for r in rows for k in ("top", "bottom", "level")
                  if r.get(f"rejected_{k}") in ("是", "否"))
        flips = sum(1 for r in rows for k in ("top", "bottom", "level")
                    if r.get(f"ai_action_flipped_{k}") == "✓")
        magclamp = sum(1 for r in rows
                       for part in (r.get("rejected_reason", "") or "").split(";")
                       if "幅度截断" in part)
        L.append(f"- 建议总数(需安全校验的动作): {sug}")
        L.append(f"- 方向翻转数: {flips}  (翻转率 "
                 f"{100.0*flips/sug:.1f}%)" if sug else "- 方向翻转数: 0")
        L.append(f"- 幅度截断数: {magclamp}")
        L.append("- 拦截数: 0 (翻转策略: 错误方向自动纠正后下发, 不拦截)")
        reasons = {}
        for r in rows:
            for part in (r.get("rejected_reason", "") or "").split(";"):
                if part:
                    reasons[part] = reasons.get(part, 0) + 1
        if reasons:
            L.append("- 安全动作分布:")
            for k, v in sorted(reasons.items()):
                L.append(f"  - {k}: {v}")
        L.append("")

        # 4 推理延迟
        lats = [r["inference_latency"] for r in rows
                if isinstance(r.get("inference_latency"), int)
                and r["inference_latency"] > 0]
        L.append("## 5. 推理延迟 (AI 实际调用)\n")
        if lats:
            L.append(f"- 平均 {sum(lats)/len(lats):.0f} ms | 最大 {max(lats)} ms"
                     f" | 最小 {min(lats)} ms | 样本 {len(lats)}\n")
        else:
            L.append("- 无有效样本\n")

        # 6 失败模式分类
        L.append("## 6. 失败模式分类\n")
        direrr = sum(1 for r in rows for k in ("top", "bottom", "level")
                     if r.get(f"direction_ok_{k}") == "✗")
        magerr = sum(1 for r in rows for k in ("top", "bottom", "level")
                     if "幅度过大" in (r.get("rejected_reason", "") or "")
                     and r.get(f"rejected_{k}") == "是")
        fmt = sum(1 for r in rows for k in ("top", "bottom", "level")
                  if r.get(f"ai_action_{k}") == "格式错误")
        comm = sum(1 for r in rows for k in ("top", "bottom", "level")
                   if r.get(f"ai_action_{k}") == "通信失败")
        # 耦合忽略: |偏差|>2 的回路数 >=2 但 AI 只覆盖了更少回路 (全快照调用行)
        coup = 0
        for r in rows:
            if r.get("sub_mode") in ("B1单回路",):
                continue
            need = sum(1 for k in ("top", "bottom", "level")
                       if abs(r.get(f"deviation_{k}", 0) or 0) >= BIG)
            got = sum(1 for k in ("top", "bottom", "level")
                      if r.get(f"ai_action_{k}") not in
                      (NOACT, NOTRIG, "格式错误", "通信失败", NA, "", None))
            if need >= 2 and got < need:
                coup += 1
        L.append(f"- 方向错误: {direrr}")
        L.append(f"- 幅度过大: {magerr}")
        L.append(f"- 耦合忽略(多回路偏差只处理了部分): {coup} 行")
        L.append(f"- 格式错误(输出不可解析): {fmt}")
        L.append(f"- 通信失败: {comm}")
        injfail = sum(1 for r in rows
                      if "注入失败" in (r.get("notes", "") or ""))
        if injfail:
            L.append(f"- 注入失败(PLC写入/回读不一致): {injfail} 行\n")
        else:
            L.append("")

        # 7 Prompt 对比 (类型 A)
        if self.exp_type == "A":
            L.append("## 7. Prompt 版本对比 (消融: 原始数值型 vs 强化自然语言型)\n")
            ver_rates = {}
            for ver in ("原始", "强化"):
                sub = [r for r in rows if r.get("prompt_version") == ver]
                ok = sum(t[0] for t in (self._rate(sub, k)
                                        for k in ("top", "bottom", "level")))
                bad = sum(t[1] for t in (self._rate(sub, k)
                                         for k in ("top", "bottom", "level")))
                rate = 100.0 * ok / (ok + bad) if (ok + bad) else None
                ver_rates[ver] = rate
                L.append(f"- {ver}Prompt: {ok}/{ok+bad} = "
                         f"{f'{rate:.1f}%' if rate is not None else 'N/A'}")
            r0, r1 = ver_rates.get("原始"), ver_rates.get("强化")
            if r0 is not None and r1 is not None:
                gain = r1 - r0
                L.append(f"- **强化 - 原始 = {gain:+.1f} 个百分点** "
                         f"(同一快照、temperature=0, 唯一变量为 Prompt 版本)\n")
            else:
                L.append("- (某一版本无有效评估单元, 无法计算差值)\n")

        # 7 实验类型 B 分组对比
        if self.exp_type == "B":
            L.append("## 8. 分组对比 (B1/B2/B3)\n")
            for sub in ("B1单回路", "B2多回路无协调", "B3多回路有协调"):
                grp = [r for r in rows if r.get("sub_mode") == sub]
                if not grp:
                    continue
                ok = sum(t[0] for t in (self._rate(grp, k)
                                        for k in ("top", "bottom", "level")))
                bad = sum(t[1] for t in (self._rate(grp, k)
                                         for k in ("top", "bottom", "level")))
                rate = 100.0 * ok / (ok + bad) if (ok + bad) else None
                rej = sum(1 for r in grp for k in ("top", "bottom", "level")
                          if r.get(f"rejected_{k}") == "是")
                L.append(f"- {sub}: 正确率 "
                         f"{f'{rate:.1f}%' if rate is not None else 'N/A'}"
                         f" ({ok}/{ok+bad}), 拦截 {rej}")
            L.append("")

        # 附: ESD 说明
        esdn = sum(1 for r in rows if r.get("esd_triggered") == 1)
        if esdn:
            L.append(f"\n> ⚠ 注: {esdn} 行记录期间 ESD 联锁触发 (极端工况), "
                     f"已自动复位后继续, 数据如实保留。")
        # 写文件
        path = self.summary_file
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(L))
        except Exception:
            path = ""
        # 收集统计供对照报告使用
        stats = self._summarize(rows)
        stats["summary_path"] = path
        stats["rows"] = len(rows)
        return stats

    def _summarize(self, rows):
        """从 rows 提取对照报告所需的核心指标"""
        raw_ok = raw_bad = 0
        flips = 0
        for key in ("top", "bottom", "level"):
            ok, bad, _ = self._rate(rows, key)
            raw_ok += ok; raw_bad += bad
            flips += sum(1 for r in rows
                         if r.get(f"ai_action_flipped_{key}") == "✓")
        total_evaled = raw_ok + raw_bad
        raw_rate = (100.0 * raw_ok / total_evaled) if total_evaled else None
        # 翻转率 = 翻转次数 / 需校验动作总数
        sug = sum(1 for r in rows for k in ("top", "bottom", "level")
                  if r.get(f"rejected_{k}") in ("是", "否"))
        flip_rate = (100.0 * flips / sug) if sug else 0.0
        # 格式错误率 = 格式错误动作数 / 需校验动作总数
        fmt = sum(1 for r in rows for k in ("top", "bottom", "level")
                  if r.get(f"ai_action_{k}") == "格式错误")
        fmt_rate = (100.0 * fmt / sug) if sug else 0.0
        # 推理延迟
        lats = [r["inference_latency"] for r in rows
                if isinstance(r.get("inference_latency"), int)
                and r["inference_latency"] > 0]
        avg_lat = (sum(lats) / len(lats)) if lats else None
        return {"raw_rate": raw_rate, "raw_ok": raw_ok, "raw_bad": raw_bad,
                "flip_rate": flip_rate, "flips": flips,
                "fmt_rate": fmt_rate, "fmt": fmt,
                "avg_latency": avg_lat}

    def _write_compare_report(self, ts):
        """学习对比对照报告: 空库(baseline) vs 种子库(seed)"""
        base = dict(self._phase_stats[0][1])
        seed = dict(self._phase_stats[1][1])
        L = [f"# 学习对比报告 (空库 vs 种子库)\n",
             f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 模型: {self.model}  |  实验类型: {self.exp_type}  |  "
             f"重复/工况: {self.reps}  |  工况数: {len(self.cases)}",
             f"- 温度: temperature=0 (可复现, 排除随机噪声)\n",
             "## 对照指标\n",
             "| 指标 | 空库 (baseline) | 种子库 (seed) | 差异 (seed - baseline) |",
             "|---|---|---|---|"]

        def fmt_pct(v):
            return f"{v:.1f}%" if v is not None else "N/A"

        def diff(a, b, is_pct=True):
            if a is None or b is None:
                return "—"
            d = b - a
            sign = "+" if d > 0 else ""
            return f"{sign}{d:.1f}{'%' if is_pct else 'ms'}"

        L.append(f"| AI原始方向正确率 | {fmt_pct(base['raw_rate'])} "
                 f"({base['raw_ok']}/{base['raw_ok']+base['raw_bad']}) | "
                 f"{fmt_pct(seed['raw_rate'])} "
                 f"({seed['raw_ok']}/{seed['raw_ok']+seed['raw_bad']}) | "
                 f"{diff(base['raw_rate'], seed['raw_rate'])} |")
        L.append(f"| 方向翻转率 | {fmt_pct(base['flip_rate'])} "
                 f"({base['flips']}次) | "
                 f"{fmt_pct(seed['flip_rate'])} ({seed['flips']}次) | "
                 f"{diff(base['flip_rate'], seed['flip_rate'])} |")
        L.append(f"| 格式错误率 | {fmt_pct(base['fmt_rate'])} "
                 f"({base['fmt']}次) | "
                 f"{fmt_pct(seed['fmt_rate'])} ({seed['fmt']}次) | "
                 f"{diff(base['fmt_rate'], seed['fmt_rate'])} |")
        base_lat = (f"{base['avg_latency']:.0f}ms"
                    if base['avg_latency'] else "N/A")
        seed_lat = (f"{seed['avg_latency']:.0f}ms"
                    if seed['avg_latency'] else "N/A")
        L.append(f"| 平均推理延迟 | {base_lat} | {seed_lat} | "
                 f"{diff(base['avg_latency'], seed['avg_latency'], False)} |")
        L.append("")
        L.append("## 数据来源\n")
        L.append(f"- 空库日志: `experiment_log_{ts}_baseline.csv`  "
                 f"({base.get('rows', 0)} 行)")
        L.append(f"- 种子库日志: `experiment_log_{ts}_seed.csv`  "
                 f"({seed.get('rows', 0)} 行)")
        L.append(f"- 空库报告: `summary_{ts}_baseline.md`")
        L.append(f"- 种子库报告: `summary_{ts}_seed.md`\n")
        L.append("> 说明: 两遍使用完全相同的工况集合与 temperature=0; "
                 "唯一变量为 Prompt 中是否注入种子案例参考段。"
                 "差异即反映 RAG 对 AI 输出方向正确率的影响。\n")
        path = os.path.join(EXP_DIR, f"compare_{ts}.md")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(L))
        except Exception:
            path = ""
        return path


def total_cases():
    return len(load_cases())
