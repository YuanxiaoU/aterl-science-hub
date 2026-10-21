# -*- coding: utf-8 -*-
"""测试: 能耗/生产双折线图 数据与模式间迁移"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMessageBox
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

app = QApplication([])
from ui.main_window import MainWindow
win = MainWindow()
win.resize(1400, 850)
win.show()
app.processEvents()
st = win.st

# ---- 1. 仿真模式: 图表在左侧 sim 布局中 (物料下方) ----
assert win._metrics_in_sim is True
assert win.metrics.parentWidget() is not None
# sim_left_layout 应包含 mat_panel(0) 和 metrics
n = win.sim_left_layout.count()
items = [win.sim_left_layout.itemAt(i).widget() for i in range(n)]
assert win.metrics in items and win.mat_panel in items
print(f"1. sim mode: metrics in left dock with material panel ({n} widgets) OK")

# ---- 2. 运行仿真, 数据进入图表 ----
st.running = True
win.btn_run.setChecked(True)
for _ in range(20):      # 4s 仿真
    win._on_loop()
app.processEvents()
assert len(win.metrics.data) > 0, "no metrics data"
t, e, p = win.metrics.data[-1]
print(f"2. metrics sampled: t={t:.1f}s energy={e:.1f}kW prod={p:.2f}m3/h OK")
# 默认蒸汽阀60% -> 能耗应明显大于0
assert e > 50.0, f"energy too low: {e}"
st.running = False

# ---- 3. 切到 PLC 模式: 图表迁移到底部, 位于事件日志与报警汇总之间 ----
win.set_mode("plc")
app.processEvents()
assert win._metrics_in_sim is False
bottom_items = [win.bottom_layout.itemAt(i).widget()
                for i in range(win.bottom_layout.count())]
assert bottom_items[0] is win.event_list
assert bottom_items[1] is win.metrics
assert bottom_items[2] is win.alarm_panel
# 与报警汇总 stretch 相同
assert win.bottom_layout.stretch(1) == win.bottom_layout.stretch(2) == 2
print("3. plc mode: metrics moved to bottom, left of alarm panel, same stretch OK")
# 数据已清空 (模式切换复位)
assert len(win.metrics.data) == 0

# 模拟连接, PLC 数据驱动图表
st.plc_connected = True
win._update_controls()
st.flows["steam"] = 0.8
st.flows["distillate"] = 0.5
st.flows["bottoms"] = 0.3
for _ in range(8):
    win._on_loop()
assert len(win.metrics.data) > 0
t, e, p = win.metrics.data[-1]
assert e > 300 and p > 3.0
print(f"4. plc-connected metrics: energy={e:.0f}kW prod={p:.2f}m3/h OK")

# ---- 5. 回到仿真模式: 图表回到左侧 ----
win.set_mode("sim")
app.processEvents()
assert win._metrics_in_sim is True
items = [win.sim_left_layout.itemAt(i).widget()
         for i in range(win.sim_left_layout.count())]
assert win.metrics in items
bottom_items = [win.bottom_layout.itemAt(i).widget()
                for i in range(win.bottom_layout.count())]
assert win.metrics not in bottom_items
print("5. back to sim mode: metrics returned to left dock OK")

# ---- 6. 中文/英文切换不崩 ----
win.apply_language("en"); app.processEvents()
win.apply_language("zh"); app.processEvents()
print("6. language switch OK")

win.close()
print("ALL METRICS TESTS PASSED")
