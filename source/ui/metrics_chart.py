# -*- coding: utf-8 -*-
"""能耗与生产指标双折线图 (双 Y 轴):
左轴 - 综合能耗 kW (再沸器蒸汽 + 预热器 + 泵功)
右轴 - 产品采出量 m3/h (塔顶 + 塔釜)
仿真模式置于左侧物料面板下方 (约2/3), PLC 模式移至底部报警栏左侧。
"""
from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox

from core import i18n

pg.setConfigOptions(background="#121a24", foreground="#d8e2ee", antialias=True)

COL_ENERGY = "#ff9d5c"
COL_PROD = "#7fe08a"


class MetricsChart(QWidget):
    def __init__(self, st, parent=None):
        super().__init__(parent)
        self.st = st
        self.data = deque(maxlen=3600)     # (t, energy_kW, prod_m3h)
        self._cum_prod = 0.0
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        box = QGroupBox(i18n.tr("metrics.title"))
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 14, 4, 4)

        self.pw = pg.PlotWidget()
        self.pw.showGrid(x=True, y=True, alpha=0.25)
        self.pw.setLabel("bottom", i18n.tr("trend.time"))
        self.pw.setLabel("left", i18n.tr("metrics.energy"), color=COL_ENERGY)
        self.pw.getAxis("left").setPen(COL_ENERGY)
        self.pw.getAxis("left").setTextPen(COL_ENERGY)
        self.pw.showAxis("right")
        self.pw.setLabel("right", i18n.tr("metrics.production"), color=COL_PROD)
        self.pw.getAxis("right").setPen(COL_PROD)
        self.pw.getAxis("right").setTextPen(COL_PROD)

        # 右轴独立 ViewBox
        self.vb2 = pg.ViewBox()
        self.pw.scene().addItem(self.vb2)
        self.pw.getAxis("right").linkToView(self.vb2)
        self.vb2.setXLink(self.pw)
        self.pw.getViewBox().sigResized.connect(self._sync_views)

        self.curve_e = pg.PlotDataItem(pen=pg.mkPen(COL_ENERGY, width=2),
                                       name=i18n.tr("metrics.energy_legend"))
        self.curve_p = pg.PlotDataItem(pen=pg.mkPen(COL_PROD, width=2),
                                       name=i18n.tr("metrics.prod_legend"))
        self.pw.addItem(self.curve_e)
        self.vb2.addItem(self.curve_p)
        legend = self.pw.addLegend(offset=(8, 8))
        legend.addItem(self.curve_e, i18n.tr("metrics.energy_legend"))
        legend.addItem(self.curve_p, i18n.tr("metrics.prod_legend"))
        v.addWidget(self.pw)
        lay.addWidget(box)

    def _sync_views(self):
        vb = self.pw.getViewBox()
        self.vb2.setGeometry(vb.sceneBoundingRect())
        self.vb2.linkedViewChanged(vb, self.vb2.XAxis)

    # ---------------- 数据 ----------------
    def update_metrics(self, dt_s=1.0):
        st = self.st
        f = st.flows
        d = st.devices
        # 综合能耗: 再沸器蒸汽(主) + 预热器电加热 + 两台泵
        energy = (f.get("steam", 0.0) * 450.0
                  + d["E101"].power / 100.0 * 120.0
                  + (d["P101"].speed + d["P102"].speed) / 200.0 * 15.0)
        # 产品采出量 (塔顶 + 塔釜), 归一化流量折算 m3/h
        prod = (f.get("distillate", 0.0) + f.get("bottoms", 0.0)) * 6.0
        t = st.sim_time
        self.data.append((t, energy, prod))
        self._cum_prod += prod * dt_s / 3600.0
        xs = [p[0] for p in self.data]
        self.curve_e.setData(xs, [p[1] for p in self.data])
        self.curve_p.setData(xs, [p[2] for p in self.data])
        self.vb2.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

    def reset(self):
        self.data.clear()
        self._cum_prod = 0.0
        self.curve_e.setData([], [])
        self.curve_p.setData([], [])
