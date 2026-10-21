# -*- coding: utf-8 -*-
"""物料系统面板: 切换物料 + 自定义物料管理 (组分/属性输入)"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QLabel, QComboBox, QPushButton, QDialog,
                               QLineEdit, QTableWidget, QTableWidgetItem,
                               QMessageBox, QHeaderView, QAbstractItemView)

from core import i18n
from core import materials as mats


class CustomMaterialDialog(QDialog):
    """自定义物料: 输入组分及属性"""
    saved = Signal()

    HEAD = ["mat.comp", "mat.frac", "mat.bp", "mat.density", "mat.hazard"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("mat.custom"))
        self.resize(560, 420)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("mat.name")))
        self.ed_name = QLineEdit()
        row.addWidget(self.ed_name)
        lay.addLayout(row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([i18n.tr(k) for k in self.HEAD])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

        brow = QHBoxLayout()
        b_add = QPushButton(i18n.tr("mat.add_comp"))
        b_add.clicked.connect(self._add_row)
        b_del = QPushButton(i18n.tr("mat.del_comp"))
        b_del.clicked.connect(self._del_row)
        b_save = QPushButton(i18n.tr("mat.save"))
        b_save.clicked.connect(self._save)
        brow.addWidget(b_add)
        brow.addWidget(b_del)
        brow.addStretch(1)
        brow.addWidget(b_save)
        lay.addLayout(brow)
        self._add_row()

    def _add_row(self, name="", frac="", bp="", dens="", hazard=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, v in enumerate([name, frac, bp, dens, hazard]):
            self.table.setItem(r, c, QTableWidgetItem(str(v)))

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _save(self):
        name = self.ed_name.text().strip()
        if not name:
            QMessageBox.warning(self, i18n.tr("confirm"), i18n.tr("mat.err_name"))
            return
        comps = []
        total = 0.0
        for r in range(self.table.rowCount()):
            def val(c, default):
                it = self.table.item(r, c)
                return it.text().strip() if it else ""
            cname = val(0)
            if not cname:
                continue
            try:
                frac = float(val(1) or 0)
                bp = float(val(2) or 100)
                dens = float(val(3) or 0.8)
            except ValueError:
                continue
            total += frac
            comps.append(mats.Component(cname, frac, bp, dens, val(4)))
        if abs(total - 100.0) > 5.0:
            QMessageBox.warning(self, i18n.tr("confirm"),
                                i18n.tr("mat.err_frac", v=total))
            return
        custom = mats.load_custom()
        custom = [m for m in custom if m.name != name]
        custom.append(mats.MaterialSystem(name, comps))
        mats.save_custom(custom)
        QMessageBox.information(self, i18n.tr("confirm"), i18n.tr("mat.saved"))
        self.saved.emit()
        self.accept()


class MaterialPanel(QWidget):
    material_changed = Signal(str)

    def __init__(self, st, parent=None):
        super().__init__(parent)
        self.st = st
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        box = QGroupBox(i18n.tr("mat.title"))
        v = QVBoxLayout(box)
        self.combo = QComboBox()
        self._reload()
        v.addWidget(self.combo)
        btn = QPushButton(i18n.tr("mat.custom"))
        btn.clicked.connect(self._open_custom)
        v.addWidget(btn)
        self.lb_info = QLabel()
        self.lb_info.setWordWrap(True)
        self.lb_info.setAlignment(Qt.AlignTop)
        v.addWidget(self.lb_info, 1)
        lay.addWidget(box)
        self.combo.currentTextChanged.connect(self._on_change)
        self._on_change(self.combo.currentText())

    def _reload(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        for m in mats.all_materials():
            self.combo.addItem(m.name)
        cur = self.st.material.name if self.st.material else None
        if cur:
            i = self.combo.findText(cur)
            if i >= 0:
                self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)

    def _on_change(self, name):
        m = mats.find_material(name)
        self.st.material = m
        lines = []
        for c in m.components:
            lines.append(f"· {c.name}: {c.frac:.0f}%  bp {c.bp}℃  ρ={c.density}  {c.hazard}")
        if m.note:
            lines.append(m.note)
        self.lb_info.setText("\n".join(lines))
        self.material_changed.emit(name)

    def _open_custom(self):
        dlg = CustomMaterialDialog(self)
        dlg.saved.connect(self._reload)
        dlg.exec()

    def retranslate(self):
        cur = self.combo.currentText()
        self.combo.blockSignals(True)
        self.combo.clear()
        for m in mats.all_materials():
            self.combo.addItem(m.name)
        i = self.combo.findText(cur)
        if i >= 0:
            self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)
