# -*- coding: utf-8 -*-
"""改进项专项测试: ESD / PLC遮罩 / 报警面板 / 建议行"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox, QLabel
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

app = QApplication([])
from ui.main_window import MainWindow
win = MainWindow()
win.resize(1400, 850)
win.show()
app.processEvents()
st = win.st

# ---- 1. ESD 紧急停车 ----
st.running = True
win.btn_run.setChecked(True)
win._esd()
app.processEvents()
assert st.running is False, "sim should pause after ESD"
for dev_id, dev in st.devices.items():
    if dev.dtype == "valve":
        assert dev.opening == 0.0, f"{dev_id} valve not closed"
    if dev.dtype == "pump":
        assert dev.running is False and dev.speed == 0.0, f"{dev_id} pump not stopped"
assert st.devices["E101"].power == 0.0, "E101 heater not tripped"
esd_events = [e for e in st.events if e["key"] == "alarm.esd"]
assert esd_events, "ESD event not logged"
print("ESD OK: all valves=0, pumps stopped, heater tripped, event logged")

# ---- 2. PLC 模式遮罩状态 ----
st.mode = "plc"
st.plc_connected = False
win.canvas.repaint()
app.processEvents()
print("PLC mode (disconnected) overlay renders OK")
st.plc_connected = True
win.canvas.repaint()
app.processEvents()
print("PLC mode (connected) banner renders OK")
st.plc_connected = False
st.mode = "sim"

# ---- 3. 报警面板刷新 ----
st.devices["T101"].alarms = [("alarm.high_press", 130.0)]
st.active_alarms = {"T101": [("alarm.high_press", 130.0)]}
win.alarm_panel.update_panel()
assert win.alarm_panel.alarm_list.count() >= 1
txt = win.alarm_panel.alarm_list.item(0).text()
assert "T101" in txt, txt
print("Alarm panel OK:", txt.strip())
st.devices["T101"].alarms = []
st.active_alarms = {}
win.alarm_panel.update_panel()

# ---- 4. 长文字建议行 ----
from ui.ai_dock import SuggestRow
long_action = {"device": "FV102", "param": "opening", "value": 45.0,
               "reason": "塔压偏高(128.5 kPa)并有继续上升趋势, 建议关小蒸汽阀开度至45%, 同时开大冷却水阀至80%, 并通知现场检查蒸汽管网压力是否波动"}
row = SuggestRow(long_action, lambda r: None, lambda r: None)
row.resize(300, 200)
app.processEvents()
labels = row.findChildren(QLabel)
assert labels and long_action["reason"] in labels[0].text()
assert labels[0].wordWrap() is True
print("SuggestRow with long text builds OK, wrap enabled:", labels[0].wordWrap())

# ---- 5. 中英文切换不崩 ----
win.apply_language("en"); app.processEvents()
win.apply_language("zh"); app.processEvents()
print("Language switch OK")

win.close()
print("ALL IMPROVEMENT TESTS PASSED")
