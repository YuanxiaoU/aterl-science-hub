# -*- coding: utf-8 -*-
"""自动化自检: 引擎推进 + 界面离屏构建 + 规则建议"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.app_state import AppState
from core.materials import all_materials
from core.simulation import SimulationEngine, compute_flows
from core.ai_advisor import rule_advice

# ---- 1. 引擎测试 ----
st = AppState()
st.material = all_materials()[0]
eng = SimulationEngine(st)
eng.reset()
st.running = True
for i in range(600):           # 600s 仿真
    eng.step(1.0)
print("sim_time =", st.sim_time)
print("T101 top=%.1f bot=%.1f P=%.1f" % (st.devices["T101"].temp, st.devices["E102"].temp, st.devices["T101"].press))
print("V101 L=%.1f V102 L=%.1f V103 L=%.1f V104 L=%.1f" % (
    st.devices["V101"].level, st.devices["V102"].level, st.devices["V103"].level, st.devices["V104"].level))
print("flows:", {k: round(v, 2) for k, v in st.flows.items()})
assert 0 < st.devices["T101"].press < 160, "pressure out of range"
assert st.devices["T101"].temp > 30, "top temp too low"
print("rules:", len(rule_advice(st)), "suggestions")

# ---- 2. 界面构建测试 ----
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
app = QApplication([])
win = MainWindow()
win.show()
app.processEvents()
# 模拟点击设备
win.open_device_dialog("T101")
app.processEvents()
# 语言切换
win.apply_language("en")
app.processEvents()
win.apply_language("zh")
app.processEvents()
# 应用动作 (注意: MainWindow 内部持有独立的 AppState, 应用后检查 win.st)
win.apply_action({"device": "FV105", "param": "opening", "value": 60.0})
assert win.st.devices["FV105"].opening == 60.0
# 模式切换 (PLC 不连接)
win.set_mode("plc"); app.processEvents()
win.set_mode("sim"); app.processEvents()
# 再推进 100 步
for i in range(100):
    eng.step(1.0)
print("UI OK")
# 绕过退出确认框
from PySide6.QtWidgets import QMessageBox
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
win.close()
print("ALL TESTS PASSED")
