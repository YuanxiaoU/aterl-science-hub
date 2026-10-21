# -*- coding: utf-8 -*-
"""修复项专项测试: 滑块回弹 / 按钮禁用 / 冻结动画 / 模式复位"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

app = QApplication([])
from ui.main_window import MainWindow
from ui.device_dialog import DeviceDialog
win = MainWindow()
win.resize(1400, 850)
win.show()
app.processEvents()
st = win.st

# ---- 1. 滑块不回弹: 拖动后未点应用, 刷新不得覆盖 ----
win.open_device_dialog("FV102")
app.processEvents()
dlg = win._dialogs["FV102"]
orig = st.devices["FV102"].opening
dlg.sl.setValue(88)          # 用户拖到 88
for _ in range(4):          # 模拟 2 秒定时刷新
    dlg._refresh()
assert dlg.sp.value() == 88, f"slider snapped back: {dlg.sp.value()}"
print(f"1. slider holds at 88 after refresh (device still {orig}) OK")
dlg._apply_valve()          # 点应用
assert st.devices["FV102"].opening == 88
dlg._refresh()
assert dlg.sp.value() == 88
print("1b. after apply, control syncs to device OK")

# 泵转速同理
win.open_device_dialog("P101")
app.processEvents()
dlg2 = win._dialogs["P101"]
dlg2.sp_speed.setValue(66)
for _ in range(3):
    dlg2._refresh()
assert dlg2.sp_speed.value() == 66, "pump speed spun back"
print("1c. pump speed spinbox holds OK")
dlg2.close()

# ---- 2. PLC 未连接: 三按钮禁用变暗 ----
win.set_mode("plc")
app.processEvents()
assert st.mode == "plc" and st.plc_connected is False
assert not win.btn_run.isEnabled(), "run should be disabled"
assert not win.btn_esd.isEnabled(), "esd should be disabled"
assert not win.btn_reset.isEnabled(), "reset should be disabled"
print("2. run/esd/reset disabled when PLC not connected OK")
# 模式切换后设备回到默认静止状态 (FV102 被测试1改为88, 复位后应回到默认60)
assert st.running is False
assert st.devices["FV102"].opening == 60.0, "devices not reset to default"
assert st.sim_time == 0.0, "sim_time not reset"
print("2b. devices at static default state after mode switch OK")

# ---- 3. 冻结: 未连接时粒子相位不推进 ----
phase0 = win.canvas._phase
for _ in range(5):
    win._on_loop()
assert win.canvas._phase == phase0, "particles advanced while disconnected!"
print("3. particles frozen while PLC disconnected OK")

# 模拟连接成功
st.plc_connected = True
win._update_controls()
app.processEvents()
assert win.btn_run.isEnabled() and win.btn_esd.isEnabled()
print("3b. buttons enabled after connected OK")
phase0 = win.canvas._phase
for _ in range(5):
    win._on_loop()
assert win.canvas._phase > phase0, "particles should move when connected"
print("3c. particles move after connected OK")

# ---- 4. 仿真模式: 暂停/急停冻结, 恢复继续 ----
win.set_mode("sim")
app.processEvents()
st.plc_connected = False
st.running = True
win.btn_run.setChecked(True)
for _ in range(3):
    win._on_loop()
p_run = win.canvas._phase
t_run = st.sim_time
# 暂停
st.running = False
win.btn_run.setChecked(False)
p_paused = win.canvas._phase
for _ in range(5):
    win._on_loop()
assert win.canvas._phase == p_paused, "particles moved while paused"
assert st.sim_time == t_run, "sim time advanced while paused"
print("4. particles+data frozen on pause OK")
# 急停
st.running = True
win.btn_run.setChecked(True)
for _ in range(3):
    win._on_loop()
win._esd()
app.processEvents()
assert st.running is False
p_esd = win.canvas._phase
for _ in range(5):
    win._on_loop()
assert win.canvas._phase == p_esd, "particles moved after ESD"
for dev_id, dev in st.devices.items():
    if dev.dtype == "valve":
        assert dev.opening == 0.0
print("4b. ESD freezes everything and closes valves OK")
# 恢复
st.running = True
win.btn_run.setChecked(True)
p_before = win.canvas._phase
for _ in range(3):
    win._on_loop()
assert win.canvas._phase > p_before, "particles did not resume"
print("4c. resume continues particles OK")

# ---- 5. 横幅两行文本 ----
from core import i18n
assert "\n" in i18n.tr("plc.waiting")
st.mode = "plc"; st.plc_connected = False
win.canvas.repaint()
app.processEvents()
st.mode = "sim"
print("5. two-line PLC banner renders OK")

win.close()
print("ALL FIX TESTS PASSED")
