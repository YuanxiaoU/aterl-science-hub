# -*- coding: utf-8 -*-
"""Snap7 (S7) 协议离屏测试: stub 客户端验证读解析/写回/界面切换"""
import os
import sys
import struct
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal

app = QApplication([])

# ---------- 1) reg_map_rows S7 地址格式 ----------
from core.plc import reg_map_rows, s7_word_addr, S7_DB_DEFAULT
rows = reg_map_rows("s7")
assert all(r[2].startswith(f"DB{S7_DB_DEFAULT}.DBW ") for r in rows), rows[0]
first = rows[0]
assert first[2] == f"DB{S7_DB_DEFAULT}.DBW 0", first
print("1. reg_map_rows s7 OK:", first[0], first[2])

# ---------- 2) stub snap7 模块注入 ----------
from core.app_state import DEVICE_ORDER, DEVICE_DEFS

N_BYTES = 10 * 2 * len(DEVICE_DEFS)


SHARED_BUF = bytearray(N_BYTES)


class FakeClient:
    instances = []

    def __init__(self):
        self.buf = SHARED_BUF          # 与 worker 实例共享, 便于预填/断言
        self._conn = False
        self.writes = []
        FakeClient.instances.append(self)

    def connect(self, address, rack, slot, tcp_port=102):
        self.address, self.rack, self.slot = address, rack, slot
        self._conn = True
        return True

    def get_connected(self):
        return self._conn

    def read_area(self, area, db_number, start, size):
        return bytearray(self.buf[start:start + size])

    def write_area(self, area, db_number, start, data):
        self.buf[start:start + len(data)] = data
        self.writes.append((db_number, start, bytes(data)))
        return 0

    # ---- REAL 点表 (grad 布局) ----
    REAL_STORE = {}

    def db_read(self, db, start, size=4):
        return bytearray(FakeClient.REAL_STORE.get((db, start), bytearray(4)))

    def db_write(self, db, start, data):
        FakeClient.REAL_STORE[(db, start)] = bytes(data)
        self.writes.append((db, start, bytes(data)))
        return 0

    def disconnect(self):
        self._conn = False

    def destroy(self):
        pass


fake_snap7 = types.ModuleType("snap7")
fake_client_mod = types.ModuleType("snap7.client")
fake_client_mod.Client = FakeClient
fake_type_mod = types.ModuleType("snap7.type")


class Areas:
    DB = "DB-SENTINEL"


fake_type_mod.Areas = Areas
fake_snap7.client = fake_client_mod
fake_snap7.type = fake_type_mod
sys.modules["snap7"] = fake_snap7
sys.modules["snap7.client"] = fake_client_mod
sys.modules["snap7.type"] = fake_type_mod
print("2. stub snap7 injected")

import core.plc as plc_mod

# 错误诊断分类
assert "超时" in plc_mod.diagnose_s7_error("1.2.3.4", TimeoutError())
assert "拒绝" in plc_mod.diagnose_s7_error("1.2.3.4", ConnectionRefusedError())
assert "握手" in plc_mod.diagnose_s7_error("1.2.3.4", Exception("Connection closed by peer"))
assert "不可达" in plc_mod.diagnose_s7_error("1.2.3.4", OSError("No route to host"))
print("2b. diagnose_s7_error classification OK")

# 预填 DB 数据: 每设备 word0=温度x10, word1=压力x10...
for i in range(len(DEVICE_DEFS)):
    struct.pack_into(">H", SHARED_BUF, i * 20, 250 + i)      # temp 25.0+
    struct.pack_into(">H", SHARED_BUF, i * 20 + 2, 100 + i)  # press 10.0+

# ---------- 3) PLCWorker S7 运行 ----------
from core.plc import PLCWorker

cfg = {"plc": {"proto": "s7", "host": "192.168.0.10", "rack": 0, "slot": 1,
               "db": 100, "s7_layout": "block", "interval": 100}}
worker = PLCWorker(cfg)
got = {"states": None, "status": []}


class Bridge(QThread):
    states = Signal(dict)
    st = Signal(str)

    def __init__(self):
        super().__init__()
        self.s = None

    def run(self):
        pass


bridge_states = {}


def on_states(states):
    bridge_states.update(states)


def on_status(t):
    got["status"].append(t)


worker.state_ready.connect(on_states)
worker.status.connect(on_status)
worker.start()
worker.write_param("FV101", "opening", 77)
worker.write_param("P101", "speed", 65)

w_fv_probe = s7_word_addr(DEVICE_ORDER["FV101"], 3)
for _ in range(150):
    app.processEvents()
    QThread.msleep(20)
    if bridge_states and SHARED_BUF[w_fv_probe] == 77:
        break

worker.stop_worker()
worker.wait(3000)

assert bridge_states, f"no states received, status={got['status']}"
c = FakeClient.instances[-1]
assert c.address == "192.168.0.10" and c.rack == 0 and c.slot == 1, (c.address, c.rack, c.slot)

dev0, dtype0 = DEVICE_DEFS[0]
st0 = bridge_states[dev0]
assert abs(st0["temp"] - 25.0) < 0.01, st0
assert abs(st0["press"] - 10.0) < 0.01, st0
print("3. S7 read/parse OK:", dev0, st0)

# 写回校验: FV101 opening -> word3, P101 speed -> word4 (大端)
assert ("FV101" in DEVICE_ORDER) and ("P101" in DEVICE_ORDER)
w_fv = s7_word_addr(DEVICE_ORDER["FV101"], 3)
w_p1 = s7_word_addr(DEVICE_ORDER["P101"], 4)
w_fv_val = struct.unpack_from(">H", bytes(c.buf), w_fv)[0]
w_p1_val = struct.unpack_from(">H", bytes(c.buf), w_p1)[0]
assert w_fv_val == 77, w_fv_val
assert w_p1_val == 65, w_p1_val
assert any(db == 100 and start == w_fv for db, start, _ in c.writes)
print("4. S7 write-back OK: FV101 opening=77 @DB100.DBW", w_fv,
      "| P101 speed=65 @DB100.DBW", w_p1)

# ---------- 3b) PLCWorker grad 通用点表 (毕设 DB1/DB2 布局, config 驱动) ----------
from core.plc import get_tags, DEFAULT_TAGS

FakeClient.REAL_STORE.clear()


def put_real(db, off, v):
    FakeClient.REAL_STORE[(db, off)] = struct.pack(">f", float(v))


put_real(1, 0, 78.0)      # 塔顶温度
put_real(1, 8, 105.0)     # 塔釜温度
put_real(1, 12, 101.3)    # 塔顶压力
put_real(1, 28, 5.0)      # 回流量满量程 -> 开度 100%
put_real(2, 0, 77.5)      # 温度设定

# 自定义点表 (模拟用户编辑 config): 含 INT 类型 + 线性反算写回
custom_tags = [
    {"dev": "T101", "field": "temp", "db": 1, "off": 0, "dtype": "real",
     "rw": "R", "scale": 1.0, "offset": 0.0},
    {"dev": "E102", "field": "temp", "db": 1, "off": 8, "dtype": "real",
     "rw": "R", "scale": 1.0, "offset": 0.0},
    {"dev": "T101", "field": "press", "db": 1, "off": 12, "dtype": "real",
     "rw": "R", "scale": 1.0, "offset": 0.0},
    {"dev": "FV102", "field": "opening", "db": 1, "off": 28, "dtype": "real",
     "rw": "R", "scale": 22.222222, "offset": -11.111111},
    {"dev": "E102", "field": "power", "db": 2, "off": 0, "dtype": "real",
     "rw": "R/W", "scale": 1.0, "offset": 0.0},
]
cfg_grad = {"plc": {"proto": "s7", "host": "192.168.0.1", "rack": 0, "slot": 1,
                    "s7_layout": "grad", "interval": 100, "tags": custom_tags}}
assert get_tags(cfg_grad) is custom_tags          # config 优先
assert get_tags({"plc": {}}) == DEFAULT_TAGS or len(get_tags({"plc": {}})) == 5
gw = PLCWorker(cfg_grad)
gst = {}
gw.state_ready.connect(lambda s: gst.update(s))
gw.start()
gw.write_param("E102", "power", 76.0)
for _ in range(150):
    app.processEvents()
    QThread.msleep(20)
    sp = FakeClient.REAL_STORE.get((2, 0))
    if gst and sp and abs(struct.unpack(">f", sp)[0] - 76.0) < 0.01:
        break
gw.stop_worker()
gw.wait(3000)

assert abs(gst["T101"]["temp"] - 78.0) < 0.01, gst
assert abs(gst["T101"]["press"] - 101.3) < 0.01, gst
assert abs(gst["E102"]["temp"] - 105.0) < 0.01, gst
assert abs(gst["E102"]["power"] - 77.5) < 0.01, gst
assert abs(gst["FV102"]["opening"] - 100.0) < 0.05, gst
assert abs(struct.unpack(">f", FakeClient.REAL_STORE[(2, 0)])[0] - 76.0) < 0.01

# INT 标签 + 反算写回
FakeClient.REAL_STORE[(3, 10)] = struct.pack(">h", 500)   # 原始 500, x0.1 = 50.0
int_tags = [{"dev": "P101", "field": "speed", "db": 3, "off": 10, "dtype": "int",
             "rw": "R/W", "scale": 0.1, "offset": 0.0}]
iw = PLCWorker({"plc": {"proto": "s7", "host": "x", "rack": 0, "slot": 1,
                        "s7_layout": "grad", "interval": 100, "tags": int_tags}})
ist = {}
iw.state_ready.connect(lambda s: ist.update(s))
iw.start()
iw.write_param("P101", "speed", 80.0)       # 80.0/0.1 -> 原始 800
for _ in range(100):
    app.processEvents(); QThread.msleep(20)
    if ist:
        break
iw.stop_worker(); iw.wait(3000)
assert abs(ist["P101"]["speed"] - 50.0) < 0.01, ist
assert struct.unpack(">h", FakeClient.REAL_STORE[(3, 10)])[0] == 800
grows = reg_map_rows("grad", custom_tags)
assert any("DB1.DBD 0 (REAL)" in r[2] for r in grows)
assert any("DB2.DBD 0 (REAL)" in r[2] for r in grows)
print("3b. generic tags OK: REAL/INT read, linear scale, inverse write, config-driven")

# ---------- 4) 界面: 协议切换与配置持久化 ----------
from ui.plc_panel import PlcPanel
from core.config import load_config

cfg2 = load_config()
panel = PlcPanel(cfg2)

idx = panel.cmb_proto.findData("s7")
assert idx >= 0, "s7 option missing"
panel.cmb_proto.setCurrentIndex(idx)   # 默认 grad 布局
vis = lambda w: not w.isHidden()
assert vis(panel.sp_rack) and vis(panel.sp_slot) and vis(panel.cmb_layout)
assert not vis(panel.sp_db)            # grad 布局不需要 DB 号
assert not vis(panel.sp_port) and not vis(panel.ed_com)
assert not vis(panel.sp_slave)
texts = [panel.table.item(r, 2).text() for r in range(panel.table.rowCount())]
assert all("(REAL)" in t for t in texts), texts[:5]
assert any(t.startswith("DB1.DBD") for t in texts) and any(t.startswith("DB2.DBD") for t in texts)
print("5a. panel s7+grad OK, table shows REAL tags")

# 切到 block 连续寄存器布局
bi = panel.cmb_layout.findData("block")
panel.cmb_layout.setCurrentIndex(bi)
assert vis(panel.sp_db)
texts = [panel.table.item(r, 2).text() for r in range(panel.table.rowCount())]
assert all(t.startswith("DB100.DBW") for t in texts), texts[:3]
print("5b. panel s7+block OK, table shows DBW addresses, DB spin visible")

panel.cmb_layout.setCurrentIndex(panel.cmb_layout.findData("grad"))

panel.sp_rack.setValue(2)
panel.sp_slot.setValue(3)
panel.sp_db.setValue(200)
panel.ed_host.setText("192.168.0.55")
panel.apply_to_cfg()
assert cfg2["plc"]["proto"] == "s7" and cfg2["plc"]["rack"] == 2
assert cfg2["plc"]["slot"] == 3 and cfg2["plc"]["db"] == 200
assert cfg2["plc"]["s7_layout"] == "grad"
assert cfg2["plc"]["host"] == "192.168.0.55"
print("6. apply_to_cfg OK:", {k: cfg2["plc"][k] for k in ("proto", "host", "rack", "slot", "s7_layout")})

# modbus 地址表恢复
panel.cmb_proto.setCurrentIndex(0)
t0 = panel.table.item(0, 2).text()
assert t0.isdigit(), t0
print("7. table back to modbus regs:", t0)

# ---------- 8) 点表编辑器 ----------
from ui.tag_editor import TagEditorDialog
from core.plc import DEFAULT_TAGS

dlg = TagEditorDialog([dict(t) for t in DEFAULT_TAGS])
assert dlg.table.rowCount() == len(DEFAULT_TAGS)
# 读首行默认值 (T101 / temp / DB1 / off0 / real / R)
g0 = lambda c: dlg.table.cellWidget(0, c)
assert g0(0).currentData() == "T101" and g0(2).value() == 1 and g0(4).currentData() == "real"
# 添加一行并配置为 INT 可写
dlg._add_row()
r = dlg.table.rowCount() - 1
dlg.table.cellWidget(r, 0).setCurrentIndex(dlg.table.cellWidget(r, 0).findData("P101"))
dlg.table.cellWidget(r, 1).setCurrentIndex(dlg.table.cellWidget(r, 1).findData("speed"))
dlg.table.cellWidget(r, 2).setValue(5)
dlg.table.cellWidget(r, 3).setValue(20)
dlg.table.cellWidget(r, 4).setCurrentIndex(dlg.table.cellWidget(r, 4).findData("int"))
dlg.table.cellWidget(r, 5).setCurrentIndex(dlg.table.cellWidget(r, 5).findData("R/W"))
new_tags = dlg.tags
last = new_tags[-1]
assert last["dev"] == "P101" and last["db"] == 5 and last["off"] == 20
assert last["dtype"] == "int" and last["rw"] == "R/W"
# 删除该行 + 恢复默认
dlg.table.selectRow(r)
dlg._del_row()
assert dlg.table.rowCount() == len(DEFAULT_TAGS)
dlg._load([dict(t) for t in DEFAULT_TAGS])
assert dlg.table.rowCount() == len(DEFAULT_TAGS)
# 自定义点表驱动映射表
custom = [{"dev": "V101", "field": "level", "db": 9, "off": 4, "dtype": "int",
           "rw": "R", "scale": 0.01, "offset": 0.0}]
rows2 = reg_map_rows("grad", custom)
assert rows2[0][2] == "DB9.DBW 4 (INT) ×0.01", rows2[0]
print("8. tag editor OK: add/delete/default/custom mapping")

print("ALL S7 TESTS PASSED")
