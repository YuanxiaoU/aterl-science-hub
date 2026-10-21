# -*- coding: utf-8 -*-
"""测试: 速度下拉档位 + 面板贴边"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox, QComboBox
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

app = QApplication([])
from ui.main_window import MainWindow, SPEED_OPTIONS
win = MainWindow()
win.resize(1400, 850)
win.show()
app.processEvents()

# ---- 1. 速度控件为下拉框, 默认 x1 ----
assert isinstance(win.cb_speed, QComboBox)
assert win.cb_speed.count() == len(SPEED_OPTIONS) == 6
assert win.st.speed == 1.0
print(f"1. speed combo: {[win.cb_speed.itemText(i) for i in range(win.cb_speed.count())]}")

# 切换档位生效
for idx, f in enumerate(SPEED_OPTIONS):
    win.cb_speed.setCurrentIndex(idx)
    assert abs(win.st.speed - f) < 1e-9, f"speed {win.st.speed} != {f}"
print("2. all speed gears apply correctly OK")

# 速度影响仿真步长
win.cb_speed.setCurrentIndex(SPEED_OPTIONS.index(4.0))
st = win.st
st.running = True
win.btn_run.setChecked(True)
t0 = st.sim_time
for _ in range(10):   # 10 * 0.2s * x4 = 8s 仿真
    win._on_loop()
assert abs(st.sim_time - t0 - 8.0) < 0.5, f"sim_time advanced {st.sim_time - t0}"
print(f"3. x4 gear advances sim 8s in 10 loops (got {st.sim_time - t0:.1f}s) OK")
st.running = False

# ---- 4. 面板贴边: 外边距收紧 ----
ml, mt, mr, mb = win.sim_left_layout.getContentsMargins()
assert max(ml, mt, mr, mb) <= 1, f"sim left margins {ml,mt,mr,mb}"
ml2, mt2, mr2, mb2 = win.ai_dock_w.layout().getContentsMargins()
assert max(ml2, mt2, mr2, mb2) <= 2, f"ai dock margins {ml2,mt2,mr2,mb2}"
ml3, mt3, mr3, mb3 = win.mat_panel.layout().getContentsMargins()
assert max(ml3, mt3, mr3, mb3) <= 2
ml4, mt4, mr4, mb4 = win.metrics.layout().getContentsMargins()
assert max(ml4, mt4, mr4, mb4) <= 1
print("4. all dock panel outer margins tightened to edge OK")

# 左侧停靠栏无标题条
assert win.dock_left.titleBarWidget() is not None
print("5. left dock title bar removed (flush to edge) OK")

# ---- 6. 模式切换/语言切换不崩 ----
win.set_mode("plc"); app.processEvents()
ml5, mt5, mr5, mb5 = win.plc_panel.layout().getContentsMargins()
assert max(ml5, mt5, mr5, mb5) <= 2
win.set_mode("sim"); app.processEvents()
win.apply_language("en"); app.processEvents()
assert win.cb_speed.itemText(0) == "×0.25"
win.apply_language("zh"); app.processEvents()
assert win.lb_speed.text().startswith(("运行速度", "sim.speed")) or ":" in win.lb_speed.text()
print("6. mode/lang switch OK, combo intact")

win.close()
print("ALL SPEED/LAYOUT TESTS PASSED")
