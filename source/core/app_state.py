# -*- coding: utf-8 -*-
"""全局应用状态: 设备状态 / 历史数据 / 事件"""
import time
from collections import deque

# 设备定义: (id, 类型)  类型: tank/pump/exchanger/column/valve
DEVICE_DEFS = [
    ("V101", "tank"), ("P101", "pump"), ("E101", "exchanger"),
    ("FV101", "valve"),
    ("T101", "column"),
    ("E102", "exchanger"), ("FV102", "valve"),
    ("E103", "exchanger"), ("FV103", "valve"),
    ("V102", "tank"), ("P102", "pump"),
    ("FV104", "valve"), ("FV105", "valve"),
    ("V103", "tank"),
    ("FV106", "valve"), ("V104", "tank"),
]

DEVICE_ORDER = {d[0]: i for i, d in enumerate(DEVICE_DEFS)}


class Device:
    def __init__(self, dev_id, dtype):
        self.id = dev_id
        self.dtype = dtype
        self.temp = 25.0        # ℃
        self.press = 101.3      # kPa
        self.level = 0.0        # 储罐液位 %
        self.opening = 0.0      # 阀门开度 %
        self.speed = 0.0        # 泵转速 %
        self.running = False    # 泵运行
        self.power = 0.0        # 换热器功率 %
        self.sp_temp = None     # 温度设定值 ℃ (PLC 点表配置后才有, None=未配置)
        self.sp_level = None    # 液位设定值 % (同上)
        self.top_temp = 25.0    # 塔顶温度 (T101)
        self.alarms = []        # [(key, value)]


class AppState:
    def __init__(self):
        self.devices = {}
        for dev_id, dtype in DEVICE_DEFS:
            self.devices[dev_id] = Device(dev_id, dtype)
        self.flows = {"feed": 0.0, "vapor": 0.0, "condensate": 0.0,
                      "reflux": 0.0, "distillate": 0.0, "steam": 0.0,
                      "cooling": 0.0, "bottoms": 0.0, "top_out": 0.0,
                      "bot_out": 0.0}
        self.material = None
        self.speed = 1.0        # 仿真倍速
        self.running = False    # 仿真运行
        self.mode = "sim"       # sim / plc
        self.plc_connected = False
        self.sim_time = 0.0     # 累计运行时间 s
        self.hist = {}          # (dev, field) -> deque[(t, v)]
        self.events = deque(maxlen=400)   # 事件/报警记录
        self.active_alarms = {}           # dev -> [(key, value)]
        self.auto_ai = False
        self._interlock_latched = False
        self.esd_locked = False        # ESD 联锁锁定: True 时禁止所有写操作
        self.esd_reason = ""           # ESD 触发原因: 人工触发/超压联锁
        self.esd_trigger_val = 0       # PLC ESD_Trigger 最新值 (0正常/1联锁/2人工)
        self.esd_plc_cleared = False   # PLC 联锁已解除, 等待人工确认复位

    def reset_devices(self):
        d = self.devices
        for dev in d.values():
            dev.alarms = []
        d["V101"].level = 70.0
        d["V101"].temp = 25.0
        d["P101"].running = True
        d["P101"].speed = 80.0
        d["E101"].power = 60.0
        d["FV101"].opening = 50.0
        d["FV102"].opening = 60.0
        d["E102"].power = 60.0
        d["FV103"].opening = 70.0
        d["FV104"].opening = 60.0
        d["FV105"].opening = 35.0
        d["FV106"].opening = 40.0
        d["P102"].running = True
        d["P102"].speed = 80.0
        d["T101"].press = 101.3
        d["T101"].temp = 60.0
        d["T101"].top_temp = 60.0
        self.sim_time = 0.0
        self._interlock_latched = False

    def push_hist(self, dev_id, fieldname, t, v):
        key = (dev_id, fieldname)
        if key not in self.hist:
            self.hist[key] = deque(maxlen=7200)
        self.hist[key].append((t, v))

    def clear_hist(self):
        self.hist.clear()

    def log_event(self, key, dev=None, **params):
        self.events.append({"t": time.strftime("%H:%M:%S"),
                            "dev": dev or "", "key": key, "params": params})
