# -*- coding: utf-8 -*-
"""精馏过程动态仿真引擎 (一阶惯性环节 + 物性驱动的稳态目标)"""
import math

from .app_state import AppState
from . import i18n

T_AMBIENT = 25.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def compute_flows(d):
    """由设备状态推算各管路流量 (用于流程图动画, 归一化 0~1)"""
    p101 = d["P101"]
    feed = (0.55 * (p101.speed / 100.0) if p101.running else 0.0) * d["FV101"].opening / 100.0
    # 再沸器实际热负荷 = 蒸汽阀(FV102, 手动总阀/联锁切断) × 加热功率(E102, PID可调)
    steam = d["FV102"].opening / 100.0 * d["E102"].power / 100.0
    vapor = 0.85 * steam
    cool = d["FV103"].opening / 100.0
    condensate = vapor * (0.35 + 0.65 * min(1.0, cool * 1.4))
    p102 = d["P102"]
    reflux = (0.5 * (p102.speed / 100.0) if p102.running else 0.0) * d["FV104"].opening / 100.0
    distillate = 0.5 * d["FV105"].opening / 100.0 * (0.4 + 0.6 * min(1.0, condensate))
    bottoms = 0.5 * d["FV106"].opening / 100.0
    return {"feed": clamp(feed, 0, 1), "vapor": clamp(vapor, 0, 1),
            "condensate": clamp(condensate, 0, 1), "reflux": clamp(reflux, 0, 1),
            "distillate": clamp(distillate, 0, 1), "steam": steam,
            "cooling": cool, "bottoms": clamp(bottoms, 0, 1)}


class SimulationEngine:
    """state 由 UI 层持有, 引擎只做数值推进"""

    def __init__(self, st: AppState):
        self.st = st

    # ---------- 稳态目标 ----------
    def _targets(self):
        """由物料体系计算塔顶/塔釜目标温度"""
        m = self.st.material
        comps = sorted(m.components, key=lambda c: c.bp)
        t_light = comps[0].bp
        t_heavy = comps[-1].bp
        return t_light, t_heavy

    def reset(self):
        self.st.reset_devices()
        self.st.flows = compute_flows(self.st.devices)

    def step(self, dt):
        """推进 dt 秒 (仿真时间)"""
        st = self.st
        d = st.devices
        t_light, t_heavy = self._targets()

        # ---- 进料系统 ----
        p101, fv101 = d["P101"], d["FV101"]
        feed_flow = (1.6 * (p101.speed / 100.0) if p101.running else 0.0) * fv101.opening / 100.0
        d["V101"].level = clamp(d["V101"].level - feed_flow * dt * 0.045, 0.0, 100.0)
        d["V101"].press = 101.3
        p101.temp = d["V101"].temp
        p101.press = 101.3 + 4.0 * p101.speed / 100.0

        # ---- 预热器 E101 ----
        e101 = d["E101"]
        t_out = T_AMBIENT + 0.95 * e101.power * (1.0 if p101.running else 0.0)
        if not p101.running or fv101.opening < 1:
            t_out = e101.temp - 3.0 * dt / 60.0   # 无流动时缓慢冷却
        e101.temp += (t_out - e101.temp) * min(1.0, dt / 25.0)
        e101.press = p101.press

        # ---- 精馏塔 T101 ----
        # 再沸器: FV102 蒸汽总阀(手动/联锁) × E102 加热功率(可PID自动调节)
        t101, fv102, fv103 = d["T101"], d["FV102"], d["FV103"]
        e102 = d["E102"]
        heat_duty = fv102.opening / 100.0 * e102.power / 100.0
        boil = 3.0 * heat_duty * (0.55 + 0.45 * min(1.0, feed_flow / 0.8))
        boil_n = clamp(boil / 3.0, 0, 1)
        press_tgt = 101.3 + 16.0 * heat_duty - 7.0 * fv103.opening / 100.0
        t101.press += (press_tgt - t101.press) * min(1.0, dt / 12.0)

        cool_ok = fv103.opening / 100.0
        top_tgt = t_light + 0.30 * (t101.press - 101.3) + 9.0 * max(0.0, 0.55 - cool_ok)
        top_tgt = clamp(top_tgt, t_light - 6.0, t_heavy)
        bot_tgt = t_heavy + 0.25 * (t101.press - 101.3)
        if heat_duty < 0.04:
            bot_tgt = T_AMBIENT + 25.0   # 蒸汽阀关或功率为零则降温

        # T101.temp = 塔顶温度 (与画布/PLC/L3回路约定一致); E102.temp = 塔釜温度
        t101.temp += (top_tgt - t101.temp) * min(1.0, dt / 22.0)
        tau_b = 28.0 + 30.0 * (1.0 - boil_n)

        # ---- 冷凝器 E103 / 回流罐 V102 ----
        e103 = d["E103"]
        e103.temp = T_AMBIENT + 12.0 * (1.0 - cool_ok) + 3.0
        e103.press = t101.press - 4.0
        condensate = boil * (0.35 + 0.65 * min(1.0, cool_ok * 1.4))

        p102, fv104, fv105 = d["P102"], d["FV104"], d["FV105"]
        reflux = (1.8 * (p102.speed / 100.0) if p102.running else 0.0) * fv104.opening / 100.0
        distillate = 1.8 * fv105.opening / 100.0 * (0.4 + 0.6 * clamp(condensate / 2.5, 0, 1))
        d_v102 = (condensate - reflux - distillate) * 0.38
        d["V102"].level = clamp(d["V102"].level + d_v102 * dt, 0.0, 100.0)
        d["V102"].temp = t101.temp - 4.0
        d["V102"].press = t101.press - 8.0
        p102.temp = d["V102"].temp
        p102.press = d["V102"].press + 4.0 * p102.speed / 100.0

        # ---- 塔顶产品罐 V103 (连续采出外送) ----
        v103 = d["V103"]
        out_top = 0.55 if v103.level > 3.0 else 0.0
        v103.level = clamp(v103.level + (distillate - out_top) * 0.5 * dt, 0.0, 100.0)
        v103.temp = t101.temp - 6.0
        v103.press = 101.3

        # ---- 再沸器 E102 / 塔釜 ----
        e102 = d["E102"]
        e102.temp = bot_tgt   # 塔釜温度 = 重组分沸点附近
        e102.press = 320.0 + 4.0 * fv102.opening   # 蒸汽侧压力

        # ---- 釜液阀 / 塔釜产品罐 V104 ----
        fv106, v104 = d["FV106"], d["V104"]
        bot_out = 2.0 * fv106.opening / 100.0
        bot_in = 0.5 * feed_flow + 0.02 * boil
        v104.level = clamp(v104.level + (bot_in - bot_out * 0.35) * 0.5 * dt, 0.0, 100.0)
        v104.temp += ((e102.temp - 8.0) - v104.temp) * min(1.0, dt / 30.0)
        v104.press = 101.3

        st.flows = compute_flows(d)
        st.flows["top_out"] = out_top / 1.0
        st.flows["bot_out"] = bot_out / 2.0
        st.sim_time += dt
        self._check_alarms()

    # ---------- 报警 / 联锁 ----------
    def _check_alarms(self):
        st, d = self.st, self.st.devices
        new_alarms = {}
        for dev in d.values():
            dev.alarms = []

        def alarm(dev_id, key, value=None):
            new_alarms.setdefault(dev_id, []).append((key, value))

        if d["T101"].press > 125.0:
            alarm("T101", "alarm.high_press", d["T101"].press)
        if d["T101"].temp > self._targets()[0] + 8.0:
            alarm("T101", "alarm.high_temp", d["T101"].temp)
        for tid in ("V101", "V102", "V104"):
            lv = d[tid].level
            if lv > 90.0:
                alarm(tid, "alarm.high_level", lv)
            if lv < 10.0:
                alarm(tid, "alarm.low_level", lv)
        if d["V101"].level < 5.0 and d["P101"].running:
            alarm("P101", "alarm.pump_dry")
        if d["V102"].level < 2.0 and d["P102"].running:
            alarm("P102", "alarm.pump_dry")

        # 压力高联锁: >140 kPa 自动关蒸汽阀
        if d["T101"].press > 140.0 and not st._interlock_latched:
            st._interlock_latched = True
            d["FV102"].opening = 0.0
            st.log_event("alarm.interlock", dev="T101")
        if d["T101"].press < 132.0:
            st._interlock_latched = False

        # 新增报警 -> 事件记录
        for dev_id, lst in new_alarms.items():
            for key, val in lst:
                old = st.active_alarms.get(dev_id, [])
                if not any(k == key for k, _ in old):
                    st.log_event(key, dev=dev_id,
                                 v="" if val is None else f"{val:.1f}")
        st.active_alarms = new_alarms
        for dev_id, lst in new_alarms.items():
            d[dev_id].alarms = lst
