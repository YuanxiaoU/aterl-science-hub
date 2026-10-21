# -*- coding: utf-8 -*-
"""趋势曲线页: 运行时间 - 温度/压力/开度(液位) 曲线, 设备下拉切换"""
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QPushButton, QSplitter)

from core import i18n
from core.app_state import DEVICE_DEFS

pg.setConfigOptions(background="#121a24", foreground="#d8e2ee", antialias=True)

COLORS = ["#4fd8ff", "#ff9d5c", "#7fe08a", "#e06ad8", "#f2d24f", "#ff6a6a"]


class TrendView(QWidget):
    def __init__(self, st, parent=None):
        super().__init__(parent)
        self.st = st
        self.curves = []      # (field, PlotDataItem)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(f"<b>{i18n.tr('trend.device')}:</b>"))
        self.combo = QComboBox()
        for dev_id, _ in DEVICE_DEFS:
            self.combo.addItem(f"{dev_id} - {i18n.tr(dev_id)}", dev_id)
        self.combo.currentIndexChanged.connect(self._on_change)
        bar.addWidget(self.combo)
        bar.addStretch(1)
        btn = QPushButton(i18n.tr("act.clear_trend"))
        btn.clicked.connect(self._clear)
        bar.addWidget(btn)
        lay.addLayout(bar)

        self.p_temp = self._plot(i18n.tr("trend.temp"))
        self.p_press = self._plot(i18n.tr("trend.press"))
        self.p_open = self._plot(i18n.tr("trend.open"))
        split = QSplitter(Qt.Vertical)
        for w in (self.p_temp, self.p_press, self.p_open):
            split.addWidget(w)
        split.setSizes([300, 300, 300])
        lay.addWidget(split, 1)
        self._on_change()

    def _plot(self, title):
        pw = pg.PlotWidget()
        pw.addLegend(offset=(10, 10))
        pw.showGrid(x=True, y=True, alpha=0.25)
        pw.setLabel("bottom", i18n.tr("trend.time"))
        pw.setTitle(title, size="10pt", color="#9fc0dd")
        return pw

    def _add_curve(self, plot, field, name, dev_override=None):
        c = plot.plot(pen=pg.mkPen(COLORS[len(self.curves) % len(COLORS)], width=2),
                      name=name)
        # dev_override: 曲线取其他设备的历史 (如塔釜温度取 E102.temp)
        self.curves.append(((dev_override, field) if dev_override else field, c))

    def _on_change(self):
        dev_id = self.combo.currentData()
        for pw in (self.p_temp, self.p_press, self.p_open):
            pw.clear()
            # 清空图例
            try:
                pw.getPlotItem().legend.clear()
            except Exception:
                pass
        self.curves = []
        if not dev_id:
            return
        dev = self.st.devices[dev_id]
        dt = dev.dtype
        # 温度 (塔器: 塔顶温度=T101温度, 塔釜温度=E102温度)
        if dt == "column":
            self._add_curve(self.p_temp, "temp", i18n.tr("field.top_temp"))
            self._add_curve(self.p_temp, "temp", i18n.tr("field.bot_temp"),
                            dev_override="E102")
        else:
            self._add_curve(self.p_temp, "temp", i18n.tr("field.temp"))
        # 压力
        self._add_curve(self.p_press, "press", i18n.tr("field.press"))
        # 开度/转速/功率
        if dt == "valve":
            self._add_curve(self.p_open, "opening", i18n.tr("field.opening"))
        elif dt == "pump":
            self._add_curve(self.p_open, "speed", i18n.tr("field.speed"))
        elif dt == "exchanger":
            self._add_curve(self.p_open, "power", i18n.tr("field.power"))
        elif dt == "tank":
            self._add_curve(self.p_open, "level", i18n.tr("trend.level"))
        self.update_curves()

    def update_curves(self):
        dev_id = self.combo.currentData()
        if not dev_id:
            return
        for key, c in self.curves:
            hist = self.st.hist.get(key if isinstance(key, tuple)
                                    else (dev_id, key))
            if hist:
                xs = [pt[0] for pt in hist]
                ys = [pt[1] for pt in hist]
                c.setData(xs, ys)
            else:
                c.setData([], [])

    def _clear(self):
        self.st.clear_hist()
        self.update_curves()

    def retranslate(self):
        cur = self.combo.currentData()
        self.combo.blockSignals(True)
        self.combo.clear()
        for dev_id, _ in DEVICE_DEFS:
            self.combo.addItem(f"{dev_id} - {i18n.tr(dev_id)}", dev_id)
        if cur:
            self.combo.setCurrentIndex(max(0, self.combo.findData(cur)))
        self.combo.blockSignals(False)
        self.p_temp.setTitle(i18n.tr("trend.temp"), size="10pt", color="#9fc0dd")
        self.p_press.setTitle(i18n.tr("trend.press"), size="10pt", color="#9fc0dd")
        self.p_open.setTitle(i18n.tr("trend.open"), size="10pt", color="#9fc0dd")
        self._on_change()
