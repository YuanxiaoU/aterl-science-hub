# -*- coding: utf-8 -*-
"""控制回路表 + 分层仲裁管理器
分层策略 (每回路每拍):
  |偏差| <= 死区                 -> 输出保持
  死区 < |偏差| <= 大偏差阈值    -> PID 自动微调, 直接下发, 不打扰操作员
  |偏差| > 阈值 或 变化率超限    -> PID 继续兜底, 同时累计保持时间; 超过 hold_s 则升级请 LLM
                                    (LLM 建议仍必须人工点"执行", 执行后该回路转手动)
所有阈值/PID 参数均可在「控制回路」设置界面修改, 存 config.json -> pid.loops
"""
from .pid import PIDController, clamp

# 回路默认表 (id -> 定义)。每个执行器(MV)只归属一个回路, 杜绝抢阀。
# direction: +1 正作用(MV升→PV升: 加热功率/进料阀);
#            -1 反作用(MV升→PV降: 冷却水/回流阀/采出阀/釜液阀等排料阀)
# sp_mode: auto=按当前物料沸点自动给定; plc=读设备 sp_* 字段(sim下None时回退sp);
#          manual=用 sp 数值。回退 sp 与 PLC DB 初值保持一致 (顶77/釜104)
LOOP_DEFAULTS = {
    "L1": {"name": "loop.l1", "enabled": True, "auto": False,
           "pv_dev": "E102", "pv_field": "temp",
           "mv_dev": "E102", "mv_param": "power",
           "sp_mode": "plc", "sp_dev": "E102", "sp_field": "sp_temp",
           "sp": 104.0,
           "kp": 2.0, "ki": 0.05, "kd": 0.5, "direction": 1,
           "dead": 0.5, "big": 2.0, "rate": 1.0, "hold_s": 10.0,
           "out_min": 0.0, "out_max": 100.0, "max_step": 5.0},
    "L2": {"name": "loop.l2", "enabled": True, "auto": False,
           "pv_dev": "T101", "pv_field": "press",
           "mv_dev": "FV103", "mv_param": "opening",
           "sp_mode": "manual", "sp": 106.0,
           "kp": 1.5, "ki": 0.10, "kd": 0.0, "direction": -1,
           "dead": 2.0, "big": 15.0, "rate": 5.0, "hold_s": 10.0,
           "out_min": 5.0, "out_max": 95.0, "max_step": 5.0},
    "L3": {"name": "loop.l3", "enabled": True, "auto": False,
           "pv_dev": "T101", "pv_field": "temp",
           "mv_dev": "FV104", "mv_param": "opening",
           "sp_mode": "plc", "sp_dev": "T101", "sp_field": "sp_temp",
           "sp": 77.0,
           "kp": 1.8, "ki": 0.04, "kd": 0.3, "direction": -1,
           "dead": 0.5, "big": 2.0, "rate": 1.0, "hold_s": 10.0,
           "out_min": 5.0, "out_max": 95.0, "max_step": 5.0},
    "L4": {"name": "loop.l4", "enabled": True, "auto": False,
           "pv_dev": "V102", "pv_field": "level",
           "mv_dev": "FV105", "mv_param": "opening",
           "sp_mode": "manual", "sp": 50.0,
           "kp": 1.2, "ki": 0.02, "kd": 0.0, "direction": -1,
           "dead": 3.0, "big": 20.0, "rate": 8.0, "hold_s": 10.0,
           "out_min": 5.0, "out_max": 95.0, "max_step": 5.0},
    "L5": {"name": "loop.l5", "enabled": True, "auto": False,
           "pv_dev": "V104", "pv_field": "level",
           "mv_dev": "FV106", "mv_param": "opening",
           "sp_mode": "manual", "sp": 50.0,
           "kp": 1.2, "ki": 0.02, "kd": 0.0, "direction": -1,
           "dead": 3.0, "big": 20.0, "rate": 8.0, "hold_s": 10.0,
           "out_min": 5.0, "out_max": 95.0, "max_step": 5.0},
    "L6": {"name": "loop.l6", "enabled": False, "auto": False,
           "pv_dev": "V101", "pv_field": "level",
           "mv_dev": "FV101", "mv_param": "opening",
           "sp_mode": "manual", "sp": 60.0,
           "kp": 1.0, "ki": 0.02, "kd": 0.0, "direction": 1,
           "dead": 3.0, "big": 20.0, "rate": 8.0, "hold_s": 10.0,
           "out_min": 5.0, "out_max": 95.0, "max_step": 5.0},
}

LOOP_ORDER = ["L1", "L2", "L3", "L4", "L5", "L6"]


def get_loops(cfg):
    """生效回路表: config 覆盖默认值, 缺项自动补全 (旧配置向前兼容)"""
    saved = (cfg.get("pid") or {}).get("loops") or {}
    out = {}
    for lid in LOOP_ORDER:
        row = dict(LOOP_DEFAULTS[lid])
        row.update(saved.get(lid, {}))
        out[lid] = row
    return out


class _RT:
    """回路运行时态"""
    __slots__ = ("big_s", "prev_pv", "escalate_cd", "last_pid_case_t")

    def __init__(self):
        self.big_s = 0.0          # 大偏差累计保持时间(s, 仿真时基)
        self.prev_pv = None
        self.escalate_cd = 0.0    # 升级 LLM 的冷却计时
        self.last_pid_case_t = -1e9


class LoopManager:
    """每仿真/采集周期调用一次 update; 返回 (写动作列表, 升级LLM的回路列表)"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.loops = get_loops(cfg)
        self.pids = {lid: PIDController() for lid in LOOP_ORDER}
        self.rt = {lid: _RT() for lid in LOOP_ORDER}
        self._pend_on, self._pend_off = [], []   # 设置界面待执行的手自动切换
        self._configure_all()

    # ---------- 配置 ----------
    def _configure_all(self):
        for lid, row in self.loops.items():
            self.pids[lid].configure(row)

    def save_to_cfg(self):
        """把当前回路参数写回 cfg (设置界面点确定后调用); 过滤运行时临时键"""
        self.cfg.setdefault("pid", {})["loops"] = {
            lid: {k: v for k, v in row.items() if not k.startswith("_")}
            for lid, row in self.loops.items()}

    def reconfigure(self):
        """从 cfg 重新加载 (设置界面修改后)"""
        self.loops = get_loops(self.cfg)
        self._configure_all()

    def queue_switches(self, on_ids, off_ids):
        """设置界面确定后登记手自动切换 (reconfigure 重建 row 也不丢)"""
        self._pend_on, self._pend_off = list(on_ids), list(off_ids)

    def take_pending_switches(self, st):
        """主窗口在对话框关闭后调用: 投自动以当前阀位无扰初始化。返回 [(lid, on)]"""
        done = []
        for lid in self._pend_on:
            row = self.loops.get(lid)
            if row is None:
                continue
            cur = float(getattr(st.devices[row["mv_dev"]], row["mv_param"]))
            self.set_auto(lid, True, current_mv=cur)
            done.append((lid, True))
        for lid in self._pend_off:
            if lid in self.loops:
                self.set_auto(lid, False)
                done.append((lid, False))
        self._pend_on, self._pend_off = [], []
        return done

    def loop_of_mv(self, dev_id, param):
        """返回以该设备参数为执行器的回路 id (没有则 None)"""
        for lid, row in self.loops.items():
            if row["enabled"] and row["mv_dev"] == dev_id \
                    and row["mv_param"] == param:
                return lid
        return None

    def loops_for_device(self, dev_id):
        """该设备作为执行器的回路 (设备弹窗用)"""
        return [(lid, row) for lid, row in self.loops.items()
                if row["mv_dev"] == dev_id]

    def set_auto(self, lid, on, current_mv=None):
        row = self.loops[lid]
        row["auto"] = bool(on)
        if not on:
            self.pids[lid].reset(current_mv)
            self.rt[lid].big_s = 0.0
        else:
            # 投自动: 积分从当前阀位起步, 无扰切换
            self.pids[lid].reset(current_mv)
            self.rt[lid].prev_pv = None

    def all_manual(self):
        """急停: 全部转手动并复位 PID"""
        for lid in LOOP_ORDER:
            self.loops[lid]["auto"] = False
            self.pids[lid].reset()
            self.rt[lid].big_s = 0.0

    def reset(self):
        """仿真重置"""
        for lid in LOOP_ORDER:
            self.pids[lid].reset()
            self.rt[lid] = _RT()

    # ---------- 给定值 ----------
    def _setpoint(self, st, row):
        if row["sp_mode"] == "plc":
            # SP 从 PLC 读 (如 E102.sp_temp / T101.sp_temp); 未读到时回退到静态 sp
            dev = st.devices.get(row.get("sp_dev", row["pv_dev"]))
            if dev is not None:
                v = getattr(dev, row.get("sp_field", ""), None)
                if v is not None:
                    return float(v)
            return float(row.get("sp", 0.0))
        if row["sp_mode"] == "auto" and st.material and st.material.components:
            comps = sorted(st.material.components, key=lambda c: c.bp)
            # 按 PV 所属设备区分塔顶/塔釜: T101=塔顶(轻组分沸点), E102=塔釜(重组分沸点)
            pv_dev = row.get("pv_dev", "")
            if pv_dev == "T101" or row["pv_field"] == "top_temp":
                return float(comps[0].bp)        # 塔顶温度 -> 轻组分沸点
            return float(comps[-1].bp)           # 塔釜温度(E102) -> 重组分沸点
        return float(row["sp"])

    @staticmethod
    def _pv(st, row):
        dev = st.devices.get(row["pv_dev"])
        if dev is None:
            return None
        return getattr(dev, row["pv_field"], None)

    @staticmethod
    def _mv_now(st, row):
        return getattr(st.devices[row["mv_dev"]], row["mv_param"])

    # ---------- 主仲裁 ----------
    def update(self, st, dt, sim_time):
        """返回 (writes, escalations, pid_moves)
        writes: [{dev,param,value,lid}]; escalations: [lid...]; pid_moves: 同 writes 供案例记录"""
        writes, escalations, pid_moves = [], [], []
        for lid in LOOP_ORDER:
            row = self.loops[lid]
            rt = self.rt[lid]
            if not row["enabled"]:
                continue
            pv = self._pv(st, row)
            if pv is None:
                continue                     # PLC 模式测点未配置 -> 跳过
            sp = self._setpoint(st, row)
            cur_mv = float(self._mv_now(st, row))

            # 变化率 (单位/s, 按仿真时基)
            rate_now = 0.0
            if rt.prev_pv is not None and dt > 0:
                rate_now = abs(pv - rt.prev_pv) / dt
            rt.prev_pv = pv

            if not row["auto"]:
                rt.big_s = 0.0
                continue

            out, moved = self.pids[lid].compute(
                sp, pv, dt, True, cur_mv, dead=float(row["dead"]))

            # 大偏差 / 大变化率 -> 升级判定 (PID 不退出, 继续兜底)
            big = abs(sp - pv) > float(row["big"]) or \
                rate_now > float(row["rate"])
            if big:
                rt.big_s += dt
            else:
                rt.big_s = 0.0
            rt.escalate_cd = max(0.0, rt.escalate_cd - dt)
            if rt.big_s >= float(row["hold_s"]) and rt.escalate_cd <= 0:
                rt.escalate_cd = 30.0        # 同一回路 30s 内不重复打扰
                escalations.append(lid)

            if moved and abs(out - cur_mv) > 0.05:
                item = {"dev": row["mv_dev"], "param": row["mv_param"],
                        "value": float(out), "lid": lid,
                        "before": round(cur_mv, 2)}
                writes.append(item)
                pid_moves.append(item)
        return writes, escalations, pid_moves

    def status(self):
        """供界面显示: [{id,name,pv_dev,pv_field,mv_dev,mv_param,auto,sp,pv,mv,err}]"""
        out = []
        for lid in LOOP_ORDER:
            row = self.loops[lid]
            out.append({"id": lid, "row": row})
        return out
