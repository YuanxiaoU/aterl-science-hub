# -*- coding: utf-8 -*-
"""AI 智能顾问:
1. 本地大模型 (Ollama, http://127.0.0.1:11434) — 优先
2. 内置专家规则库 — 兜底 (未检测到本地模型时)
输出统一的 actions: [{"device","param","value","reason"}]
"""
import json
import os
import re
import threading
import time

import requests
from PySide6.QtCore import QObject, Signal

from . import i18n
from .simulation import clamp
from .config import LOG_DIR

# ===== 输出格式头 (各回路共用) =====
_FMT_HEADER = (
    "你是精馏装置的DCS工艺工程师。用户消息已用中文明确给出每个回路的当前值、设定值、"
    "偏差大小和【所需调节方向】, 你不需要自己判断正负号, 严格按给定方向输出数值即可。\n"
    "输出严格JSON(不要markdown): "
    '{"analysis":"简短工况分析","actions":[{"device":"FV104","param":"opening",'
    '"value":55,"reason":"原因"}]}。device/param只能使用下面各回路指定的执行器; '
    "value为0-100的数值; reason必须与调节方向一致; "
    "无需动作的回路不要输出; 最多3条动作。\n\n"
)

# ===== 塔顶温度回路 (独立模板) =====
SYS_TOP = (
    "【塔顶温度回路 — 执行器 FV104 回流阀】\n"
    "物理机制: FV104.opening 增大 → 塔顶温度下降; FV104.opening 减小 → 塔顶温度上升。\n"
    "操作规则:\n"
    "- 需要降温 → FV104.opening 增大, value 必须 > 当前开度\n"
    "- 需要升温 → FV104.opening 减小, value 必须 < 当前开度\n"
    "- 保持(死区内) → 不要输出 FV104 动作\n"
    "❌绝对禁止: 需要降温却减小 FV104, 或需要升温却增大 FV104。\n"
    "reason 示例: \"增大回流阀开度, 使塔顶温度下降\"。\n\n"
)

# ===== 塔釜温度回路 (独立模板) =====
SYS_BOTTOM = (
    "【塔釜温度回路 — 执行器 E102 再沸器功率】\n"
    "物理机制: E102.power 增大 → 塔釜温度上升; E102.power 减小 → 塔釜温度下降。\n"
    "操作规则:\n"
    "- 需要降温 → E102.power 减小, value 必须 < 当前功率\n"
    "- 需要升温 → E102.power 增大, value 必须 > 当前功率\n"
    "- 保持(死区内) → 不要输出 E102 动作\n"
    "❌绝对禁止: 需要降温却增大 E102.power, 或需要升温却减小 E102.power。\n"
    "reason 示例: \"减小再沸器功率, 使塔釜温度下降\"。\n\n"
)

# ===== 塔釜液位回路 (独立模板) =====
SYS_LEVEL = (
    "【塔釜液位回路 — 执行器 FV106 釜液阀】\n"
    "物理机制: FV106.opening 增大 → 釜液排出增多 → 液位下降; "
    "FV106.opening 减小 → 排出减少 → 液位上升。\n"
    "操作规则:\n"
    "- 需要降液位 → FV106.opening 增大, value 必须 > 当前开度\n"
    "- 需要升液位 → FV106.opening 减小, value 必须 < 当前开度\n"
    "- 保持(死区内) → 不要输出 FV106 动作\n"
    "❌绝对禁止: 需要降液位却减小 FV106, 或需要升液位却增大 FV106。\n"
    "reason 示例: \"增大釜液阀开度, 降低塔釜液位\"。\n\n"
)

# 全回路系统 Prompt = 格式头 + 三个独立回路模板
SYS_PROMPT = _FMT_HEADER + SYS_TOP + SYS_BOTTOM + SYS_LEVEL + (
    "【调整幅度】单次 value 与当前值之差的绝对值不得超过 10。"
)

# 回路子集用的 Prompt (如 B1 单回路实验)
SYS_PROMPT_TOP = _FMT_HEADER + SYS_TOP + \
    "【调整幅度】单次 value 与当前值之差的绝对值不得超过 10。"
SYS_PROMPT_BOTTOM = _FMT_HEADER + SYS_BOTTOM + \
    "【调整幅度】单次 value 与当前值之差的绝对值不得超过 10。"
SYS_PROMPT_LEVEL = _FMT_HEADER + SYS_LEVEL + \
    "【调整幅度】单次 value 与当前值之差的绝对值不得超过 10。"


def natural_context(st, loops=("top", "bottom", "level")):
    """构造自然语言工况描述: 直接告诉模型每个回路偏高/偏低多少、需要什么调节,
    模型无需自己判断偏差符号。返回字符串。"""
    d = st.devices
    BIG = 2.0
    lines = ["【当前工况 — 偏差与所需调节方向已计算好, 严格照此输出】"]
    idx = 0

    if "top" in loops:
        idx += 1
        t, fv = d["T101"], d["FV104"]
        sp = float(t.sp_temp if getattr(t, "sp_temp", None) is not None else 77.0)
        pv, cur = float(t.temp), float(fv.opening)
        e = pv - sp
        if abs(e) < BIG:
            state = (f"塔顶温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, "
                     f"偏差 {e:+.1f}°C 在±{BIG:.0f}°C死区内, 保持, 不要输出FV104动作")
        elif e > 0:
            state = (f"塔顶温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, 当前温度偏高 {e:.1f}°C, "
                     f"需要降温 → 增大回流阀FV104开度(当前{cur:.0f}%, "
                     f"value取{min(100.0, cur+10.0):.0f}以内且>{cur:.0f})")
        else:
            state = (f"塔顶温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, 当前温度偏低 {abs(e):.1f}°C, "
                     f"需要升温 → 减小回流阀FV104开度(当前{cur:.0f}%, "
                     f"value取{max(0.0, cur-10.0):.0f}以上且<{cur:.0f})")
        lines.append(f"{idx}. 塔顶回路: {state}。")

    if "bottom" in loops:
        idx += 1
        e_dev, h = d["E102"], d["E102"]
        sp = float(e_dev.sp_temp if getattr(e_dev, "sp_temp", None) is not None
                   else 104.0)
        pv, cur = float(e_dev.temp), float(h.power)
        e = pv - sp
        if abs(e) < BIG:
            state = (f"塔釜温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, "
                     f"偏差 {e:+.1f}°C 在死区内, 保持, 不要输出E102动作")
        elif e > 0:
            state = (f"塔釜温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, 当前温度偏高 {e:.1f}°C, "
                     f"需要降温 → 减小再沸器E102功率(当前{cur:.0f}%, "
                     f"value取{max(0.0, cur-10.0):.0f}以上且<{cur:.0f})")
        else:
            state = (f"塔釜温度 {pv:.1f}°C, 设定值 {sp:.1f}°C, 当前温度偏低 {abs(e):.1f}°C, "
                     f"需要升温 → 增大再沸器E102功率(当前{cur:.0f}%, "
                     f"value取{min(100.0, cur+10.0):.0f}以内且>{cur:.0f})")
        lines.append(f"{idx}. 塔釜回路: {state}。")

    if "level" in loops:
        idx += 1
        t, fv = d["T101"], d["FV106"]
        sp = float(t.sp_level if getattr(t, "sp_level", None) is not None else 50.0)
        pv, cur = float(t.level), float(fv.opening)
        e = pv - sp
        if abs(e) < BIG:
            state = (f"塔釜液位 {pv:.1f}%, 设定值 {sp:.1f}%, "
                     f"偏差 {e:+.1f}% 在死区内, 保持, 不要输出FV106动作")
        elif e > 0:
            state = (f"塔釜液位 {pv:.1f}%, 设定值 {sp:.1f}%, 当前液位偏高 {e:.1f}%, "
                     f"需要降液位 → 增大釜液阀FV106开度(当前{cur:.0f}%, "
                     f"value取{min(100.0, cur+10.0):.0f}以内且>{cur:.0f})")
        else:
            state = (f"塔釜液位 {pv:.1f}%, 设定值 {sp:.1f}%, 当前液位偏低 {abs(e):.1f}%, "
                     f"需要升液位 → 减小釜液阀FV106开度(当前{cur:.0f}%, "
                     f"value取{max(0.0, cur-10.0):.0f}以上且<{cur:.0f})")
        lines.append(f"{idx}. 液位回路: {state}。")

    lines.append("\n请按系统提示的格式输出JSON; 无需动作的回路不要给动作。")
    return "\n".join(lines)



def snapshot(st, device_id=None):
    """设备状态快照 (供规则库与大模型使用)"""
    devs = {}
    for dev_id, dv in st.devices.items():
        if device_id and dev_id != device_id:
            continue
        item = {"type": dv.dtype, "temp": round(dv.temp, 1),
                "press": round(dv.press, 1)}
        # 设定值 (SP): AI 需要据此计算偏差并执行【决策规则】
        for sp_field in ("sp_temp", "sp_level"):
            v = getattr(dv, sp_field, None)
            if v is not None:
                item[sp_field] = round(float(v), 1)
        if dv.dtype == "tank":
            item["level"] = round(dv.level, 1)
        if dv.dtype in ("valve",):
            item["opening"] = round(dv.opening, 1)
        if dv.dtype == "pump":
            item.update({"speed": round(dv.speed, 1), "running": dv.running})
        if dv.dtype == "exchanger":
            item["power"] = round(dv.power, 1)
        if dv.dtype == "column":
            # T101.temp = 塔顶温度 (与画布/PLC/L3一致); 塔釜温度取 E102.temp
            bot = st.devices.get("E102")
            item.update({"top_temp": round(dv.temp, 1),
                         "bot_temp": round(bot.temp, 1) if bot else round(dv.temp, 1)})
        if dv.alarms:
            item["alarms"] = [k for k, _ in dv.alarms]
        devs[dev_id] = item
    return {"sim_time_s": round(st.sim_time, 0), "devices": devs}


def _act(device, param, value, reason):
    return {"device": device, "param": param, "value": value, "reason": reason}


def rule_advice(st, device_id=None):
    """内置专家规则库: 检测异常并给出具体可执行数值"""
    d = st.devices
    acts = []
    tgt_light, tgt_heavy = None, None
    if st.material and st.material.components:
        comps = sorted(st.material.components, key=lambda c: c.bp)
        tgt_light, tgt_heavy = comps[0].bp, comps[-1].bp

    def want(dev):
        return device_id is None or dev == device_id

    lv = d["V102"].level
    if want("FV105"):
        if lv > 85.0:
            acts.append(_act("FV105", "opening", min(100.0, d["FV105"].opening + 15.0),
                             i18n.tr("ai.r.high_level", v=lv, v2=min(100.0, d["FV105"].opening + 15.0))))
        elif lv < 15.0 and d["FV105"].opening > 10.0:
            acts.append(_act("FV105", "opening", max(5.0, d["FV105"].opening - 10.0),
                             i18n.tr("ai.r.low_level", v=lv, v2=max(5.0, d["FV105"].opening - 10.0))))
        elif lv > 60.0 and d["V102"].level >= 0:
            # 预测性预警: 按当前净增速估算满罐时间
            rate = (st.flows.get("condensate", 0) - st.flows.get("reflux", 0)
                    - st.flows.get("distillate", 0)) * 0.38
            if rate > 0.005:
                mins = (100.0 - lv) / (rate * 60.0)
                if mins < 30.0 and want("FV105"):
                    acts.append(_act("FV105", "opening", min(100.0, d["FV105"].opening + 10.0),
                                     i18n.tr("ai.r.pred_level", m=mins)))
    p = d["T101"].press
    if want("FV102"):
        if p > 118.0:
            v2 = max(10.0, d["FV102"].opening - 12.0)
            acts.append(_act("FV102", "opening", v2,
                             i18n.tr("ai.r.press_high", v=p, v2=v2, v3=min(100.0, d["FV103"].opening + 10.0))))
            if want("FV103"):
                acts.append(_act("FV103", "opening", min(100.0, d["FV103"].opening + 10.0),
                                 i18n.tr("ai.r.press_high", v=p, v2=v2, v3=min(100.0, d["FV103"].opening + 10.0))))
        elif p < 96.0:
            v2 = min(100.0, d["FV102"].opening + 8.0)
            acts.append(_act("FV102", "opening", v2, i18n.tr("ai.r.press_low", v=p, v2=v2)))
        else:
            rate = st.flows.get("steam", 0) * 16.0 / 12.0  # 粗略升压速率
            if p > 112.0 and rate > 0.02:
                acts.append(_act("FV102", "opening", max(10.0, d["FV102"].opening - 8.0),
                                 i18n.tr("ai.r.pred_press", m=(140.0 - p) / (rate * 60.0))))
    if tgt_light is not None and want("FV104") and d["T101"].temp > tgt_light + 3.0:
        v2 = clamp(d["FV104"].opening + 15.0, 5.0, 95.0)
        acts.append(_act("FV104", "opening", v2,
                         i18n.tr("ai.r.top_temp_high", v=d["T101"].temp, v2=v2)))
    # 塔釜温度偏低 -> 开大蒸汽阀 FV102 (用 E102.temp 即塔釜温度)
    if tgt_heavy is not None and want("FV102") and d["E102"].temp < tgt_heavy - 4.0 and d["FV102"].opening < 95:
        v2 = min(100.0, d["FV102"].opening + 10.0)
        acts.append(_act("FV102", "opening", v2,
                         i18n.tr("ai.r.bot_temp_low", v=d["E102"].temp, v2=v2)))
    if want("V101") and d["V101"].level < 20.0:
        acts.append(_act("V101", "level", d["V101"].level,
                         i18n.tr("ai.r.feed_low", v=d["V101"].level)))
    if want("P101") and d["P101"].running and d["V101"].level < 5.0:
        acts.append(_act("P101", "running", 0, i18n.tr("ai.r.pump_dry", dev="P101")))
    if want("P102") and d["P102"].running and d["V102"].level < 3.0:
        acts.append(_act("P102", "running", 0, i18n.tr("ai.r.pump_dry", dev="P102")))
    return acts[:4]


def parse_ai_json(text):
    """从大模型输出中提取 JSON"""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        acts = []
        for a in data.get("actions", [])[:4]:
            dev = str(a.get("device", ""))
            param = str(a.get("param", "opening"))
            val = a.get("value", None)
            if param == "running":
                val = 1 if val in (1, True, "1", "true") else 0
            else:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                val = clamp(val, 0.0, 100.0)
            if dev and param in ("opening", "speed", "power", "running"):
                acts.append(_act(dev, param, val, str(a.get("reason", ""))))
        return {"analysis": str(data.get("analysis", "")).strip(), "actions": acts}
    except Exception:
        return None


class AIAdvisor(QObject):
    """后台调用 Ollama; 完成后发 suggestions_ready(actions, analysis, token)"""
    suggestions_ready = Signal(list, str, object)
    status_changed = Signal(bool, str)   # online, message

    def __init__(self, st, cfg, parent=None):
        super().__init__(parent)
        self.st = st
        self.cfg = cfg
        self.online = False
        self.models = []
        self.case_store = None       # 本地学习案例库 (由主窗口注入, None 时不检索)

    def _case_hint(self):
        """检索同物料相似历史好案例, 拼成提示词附加段"""
        if self.case_store is None:
            return ""
        try:
            cases = self.case_store.similar(self.st, k=3)
        except Exception:
            return ""
        if not cases:
            return ""
        lines = ["[历史相似工况-同物料, 效果良好, 仅供参考]"]
        for i, c in enumerate(cases, 1):
            bv = c.get("before", {}).get("vars", {})
            compact = ", ".join(f"{k.split('.')[0]}.{k.split('.')[1]}={v:g}"
                                for k, v in list(bv.items())[:8])
            lines.append(
                f"{i}. 工况: {compact}; 当时操作: {c.get('device','')}."
                f"{c.get('param','')}={c.get('value','')} "
                f"({c.get('reason','')}); 结果: {c.get('effect','')}")
        return "\n".join(lines)

    # ---- 本地模型探测 ----
    def check(self):
        def work():
            online, msg = False, ""
            try:
                r = requests.get(self.cfg["ollama_url"] + "/api/tags", timeout=2)
                data = r.json()
                self.models = [m.get("name", "") for m in data.get("models", [])]
                online = len(self.models) > 0
                msg = i18n.tr("ai.online") + f" ({', '.join(self.models[:3])})" if online \
                    else i18n.tr("ai.offline")
            except Exception:
                msg = i18n.tr("ai.offline")
            self.online = online
            try:
                self.status_changed.emit(online, msg)
            except RuntimeError:
                pass   # 窗口已销毁, 忽略退出阶段信号
        threading.Thread(target=work, daemon=True).start()

    # ---- 分析请求 ----
    def request_analysis(self, device_id=None, token=None):
        st = self.st
        if not self.online:
            acts = rule_advice(st, device_id)
            text = "\n".join(f"[{a['device']}] {a['reason']}" for a in acts) \
                or i18n.tr("ai.none")
            self.suggestions_ready.emit(acts, text, token)
            return
        snap = json.dumps(snapshot(st, device_id), ensure_ascii=False)
        hint = self._case_hint()
        # 自然语言工况指令 (直接给出偏差与调节方向) + 完整JSON供参考
        loops = ("top",) if device_id == "T101" else (
            "top", "bottom", "level")
        user_msg = (natural_context(st, loops) + "\n\n【实时数据JSON(参考)】\n"
                    + snap + ("\n\n" + hint if hint else ""))

        def work():
            model = self.cfg["ai_model"]
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": SYS_PROMPT},
                             {"role": "user", "content": user_msg}],
                "stream": False}
            # 调试: 把实际发给 Ollama 的完整 Prompt + model + 响应写入日志
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                dbg = os.path.join(LOG_DIR, "ai_prompt_debug.log")
                with open(dbg, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                            f"Ollama请求  model={model}\n")
                    f.write(f"{'='*80}\n")
                    f.write(f"--- System Prompt ---\n{SYS_PROMPT}\n\n")
                    f.write(f"--- User Message ---\n{user_msg}\n\n")
            except Exception:
                pass
            try:
                r = requests.post(self.cfg["ollama_url"] + "/api/chat",
                                  timeout=30, json=payload)
                raw_resp = r.json().get("message", {}).get("content", "")
                # 调试: 记录原始响应
                try:
                    dbg = os.path.join(LOG_DIR, "ai_prompt_debug.log")
                    with open(dbg, "a", encoding="utf-8") as f:
                        f.write(f"--- Ollama 原始响应 ---\n{raw_resp}\n\n")
                except Exception:
                    pass
                result = parse_ai_json(raw_resp)
            except Exception as e:
                try:
                    dbg = os.path.join(LOG_DIR, "ai_prompt_debug.log")
                    with open(dbg, "a", encoding="utf-8") as f:
                        f.write(f"--- 请求异常 ---\n{e}\n\n")
                except Exception:
                    pass
                result = None
            if result is None:
                acts = rule_advice(st, device_id)
                text = "\n".join(f"[{a['device']}] {a['reason']}" for a in acts) \
                    or i18n.tr("ai.none")
            else:
                acts = [a for a in result["actions"]
                        if device_id is None or a["device"] == device_id]
                text = result["analysis"] + ("\n" + "\n".join(
                    f"[{a['device']}] {a['reason']}" for a in acts) if acts else "")
                if not acts:
                    text = (text + "\n" + i18n.tr("ai.none")).strip()
            try:
                self.suggestions_ready.emit(acts, text, token)
            except RuntimeError:
                pass   # 窗口已销毁, 忽略退出阶段信号
        threading.Thread(target=work, daemon=True).start()
