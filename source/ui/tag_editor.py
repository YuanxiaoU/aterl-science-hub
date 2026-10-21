# -*- coding: utf-8 -*-
"""Snap7 点表编辑器: 增删改标签 (设备/字段/DB/偏移/类型/读写/系数/偏置), 无需改代码"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QComboBox,
                               QHeaderView, QLabel, QDoubleSpinBox)

from core import i18n
from core.app_state import DEVICE_DEFS
from core.plc import DEFAULT_TAGS

FIELDS = ["temp", "press", "level", "opening", "speed", "running", "power",
          "sp_temp", "sp_level"]
DTYPES = [("REAL (32位浮点)", "real"), ("INT (16位有符号)", "int")]
RWS = [("只读 R", "R"), ("读写 R/W", "R/W"), ("只写 W", "W")]


def _combo(options, current):
    cb = QComboBox()
    for text, data in options:
        cb.addItem(text, data)
    idx = cb.findData(current)
    cb.setCurrentIndex(max(0, idx))
    return cb


class TagEditorDialog(QDialog):
    """返回 accepted 后从 self.tags 取结果"""

    def __init__(self, tags, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("plc.tagedit.title"))
        self.resize(780, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(i18n.tr("plc.tagedit.hint")))

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            i18n.tr("plc.tagedit.dev"), i18n.tr("plc.tagedit.field"),
            "DB", i18n.tr("plc.tagedit.off"), i18n.tr("plc.tagedit.dtype"),
            i18n.tr("plc.tagedit.rw"), i18n.tr("plc.tagedit.scale"),
            i18n.tr("plc.tagedit.offset")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

        rowbtns = QHBoxLayout()
        b_add = QPushButton(i18n.tr("plc.tagedit.add"))
        b_del = QPushButton(i18n.tr("plc.tagedit.del"))
        b_def = QPushButton(i18n.tr("plc.tagedit.default"))
        b_add.clicked.connect(lambda: self._add_row())
        b_del.clicked.connect(self._del_row)
        b_def.clicked.connect(lambda: self._load([dict(t) for t in DEFAULT_TAGS]))
        rowbtns.addWidget(b_add)
        rowbtns.addWidget(b_del)
        rowbtns.addWidget(b_def)
        rowbtns.addStretch()
        lay.addLayout(rowbtns)

        btns = QHBoxLayout()
        btns.addStretch()
        b_ok = QPushButton(i18n.tr("ok"))
        b_cancel = QPushButton(i18n.tr("cancel"))
        b_ok.clicked.connect(self.accept)
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_ok)
        btns.addWidget(b_cancel)
        lay.addLayout(btns)

        self._load(tags)

    def _load(self, tags):
        self.table.setRowCount(0)
        for t in tags:
            self._add_row(t)

    def _add_row(self, t=None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        t = t or {}
        dev_opts = [(d[0], d[0]) for d in DEVICE_DEFS]
        self.table.setCellWidget(r, 0, _combo(dev_opts, t.get("dev", "T101")))
        self.table.setCellWidget(r, 1, _combo(
            [(i18n.tr(f"field.{f}"), f) for f in FIELDS],
            t.get("field", "temp")))

        sp_db = _int_spin(0, 65535, int(t.get("db", 1)))
        sp_off = _int_spin(0, 65534, int(t.get("off", 0)))
        self.table.setCellWidget(r, 2, sp_db)
        self.table.setCellWidget(r, 3, sp_off)
        self.table.setCellWidget(r, 4, _combo(DTYPES, t.get("dtype", "real")))
        self.table.setCellWidget(r, 5, _combo(RWS, t.get("rw", "R")))

        sp_s = QDoubleSpinBox()
        sp_s.setRange(-1e6, 1e6)
        sp_s.setDecimals(6)
        sp_s.setValue(float(t.get("scale", 1.0)))
        sp_o = QDoubleSpinBox()
        sp_o.setRange(-1e9, 1e9)
        sp_o.setDecimals(4)
        sp_o.setValue(float(t.get("offset", 0.0)))
        self.table.setCellWidget(r, 6, sp_s)
        self.table.setCellWidget(r, 7, sp_o)

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    @property
    def tags(self):
        out = []
        for r in range(self.table.rowCount()):
            g = lambda c: self.table.cellWidget(r, c)
            out.append({
                "dev": g(0).currentData(),
                "field": g(1).currentData(),
                "db": g(2).value(),
                "off": g(3).value(),
                "dtype": g(4).currentData(),
                "rw": g(5).currentData(),
                "scale": g(6).value(),
                "offset": g(7).value(),
            })
        return out


def _int_spin(lo, hi, val):
    from PySide6.QtWidgets import QSpinBox
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    return sp
