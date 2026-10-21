# -*- coding: utf-8 -*-
"""控制回路设置: 每个 PID 回路的启用/手自动/给定/PID参数/分层阈值/输出限幅均可界面修改"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QCheckBox, QDoubleSpinBox,
                               QPushButton, QHeaderView, QLabel)

from core import i18n
from core.loops import LOOP_ORDER, LOOP_DEFAULTS

COLS = [
    ("enabled", 52), ("auto", 52), ("name", 190), ("sp_mode", 58),
    ("sp", 72), ("kp", 64), ("ki", 64), ("kd", 64),
    ("dead", 62), ("big", 66), ("rate", 74), ("hold_s", 64),
    ("out_min", 62), ("out_max", 62), ("max_step", 62),
]
SP_KEYS = {"kp": (0, 20, 2), "ki": (0, 5, 3), "kd": (0, 10, 2),
           "dead": (0, 50, 1), "big": (0, 100, 1), "rate": (0, 50, 2),
           "hold_s": (2, 120, 0), "out_min": (0, 100, 1),
           "out_max": (0, 100, 1), "max_step": (0, 30, 1),
           "sp": (-50, 400, 1)}


class LoopDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.mgr = manager
        self.setWindowTitle(i18n.tr("loop.dlg_title"))
        self.resize(1350, 380)
        self._w = {}        # (lid,key) -> widget
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        hint = QLabel(i18n.tr("loop.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#1c4e80; font-size:11px;")
        lay.addWidget(hint)

        headers = [i18n.tr("loop.col." + k) for k, _w in COLS]
        self.tbl = QTableWidget(len(LOOP_ORDER), len(COLS))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setStretchLastSection(False)

        for r, lid in enumerate(LOOP_ORDER):
            row = self.mgr.loops[lid]
            for c, (key, w) in enumerate(COLS):
                if key == "name":
                    item = QTableWidgetItem(self._loop_text(row))
                    item.setFlags(Qt.ItemIsEnabled)
                    self.tbl.setItem(r, c, item)
                    continue
                if key in ("enabled", "auto", "sp_mode"):
                    cb = QCheckBox()
                    if key == "sp_mode":
                        is_plc = row["sp_mode"] == "plc"
                        cb.setChecked(row["sp_mode"] == "auto")
                        # plc 模式: SP 来自 PLC, 锁定自动给定勾选并禁用
                        cb.setEnabled(row["pv_field"] in ("temp", "top_temp")
                                      and not is_plc)
                        cb.setToolTip("设定值随 PLC 读取" if is_plc else "")
                    else:
                        cb.setChecked(bool(row[key]))
                    cb.setStyleSheet("margin-left:14px;")
                    self.tbl.setCellWidget(r, c, cb)
                    self._w[(lid, key)] = cb
                else:
                    lo, hi, dec = SP_KEYS[key]
                    sp = QDoubleSpinBox()
                    sp.setRange(lo, hi)
                    sp.setDecimals(dec)
                    sp.setValue(float(row[key]))
                    sp.setSingleStep(0.1 if dec else 1.0)
                    # plc 模式下 SP 由 PLC 给定, 禁用手动输入
                    if key == "sp" and row.get("sp_mode") == "plc":
                        sp.setEnabled(False)
                        sp.setToolTip(f"设定值来自 PLC ({row.get('sp_dev','')}."
                                      f"{row.get('sp_field','')})")
                    self.tbl.setCellWidget(r, c, sp)
                    self._w[(lid, key)] = sp
        lay.addWidget(self.tbl, 1)

        row = QHBoxLayout()
        b_default = QPushButton(i18n.tr("loop.restore"))
        b_default.clicked.connect(self._restore_defaults)
        row.addWidget(b_default)
        row.addStretch(1)
        b_ok = QPushButton(i18n.tr("confirm"))
        b_ok.clicked.connect(self._accept)
        b_cancel = QPushButton(i18n.tr("loop.cancel"))
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        lay.addLayout(row)

    @staticmethod
    def _loop_text(row):
        pv = f"{row['pv_dev']} {i18n.tr('field.' + row['pv_field'])}"
        mv = f"{row['mv_dev']} {i18n.tr('field.' + row['mv_param'])}"
        arrow = "→" if i18n.get_lang() == "zh" else "->"
        return f"{pv}  {arrow}  {mv}"

    def _restore_defaults(self):
        for r, lid in enumerate(LOOP_ORDER):
            d = LOOP_DEFAULTS[lid]
            for c, (key, _w) in enumerate(COLS):
                if key == "name":
                    continue
                w = self._w.get((lid, key))
                if w is None:
                    continue
                if isinstance(w, QCheckBox):
                    if key == "sp_mode":
                        w.setChecked(d["sp_mode"] == "auto")
                    else:
                        w.setChecked(bool(d[key]))
                else:
                    w.setValue(float(d[key]))

    def _accept(self):
        # reconfigure 会从 cfg 重建 row, 故手自动切换用 manager 的队列登记,
        # 主窗口在对话框关闭后按当前阀位做无扰初始化
        on_ids, off_ids = [], []
        for lid in LOOP_ORDER:
            row = self.mgr.loops[lid]
            was_auto = bool(row["auto"])
            for key in ("enabled", "auto", "sp_mode"):
                w = self._w.get((lid, key))
                if w is not None:
                    if key == "sp_mode":
                        # plc 模式的回路保持 plc (勾选框被禁用, 不可改)
                        if row.get("sp_mode") == "plc":
                            row[key] = "plc"
                        else:
                            row[key] = "auto" if w.isChecked() else "manual"
                    else:
                        row[key] = bool(w.isChecked())
            for key in SP_KEYS:
                w = self._w.get((lid, key))
                if w is not None:
                    row[key] = float(w.value())
            if not was_auto and row["auto"]:
                on_ids.append(lid)
            elif was_auto and not row["auto"]:
                off_ids.append(lid)
        self.mgr.save_to_cfg()
        self.mgr.reconfigure()
        self.mgr.queue_switches(on_ids, off_ids)
        self.accept()
