# -*- coding: utf-8 -*-
"""PLC 连接配置面板: 协议/端口输入 + 连接控制 + 寄存器映射表"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QGroupBox, QLabel, QComboBox, QLineEdit,
                               QSpinBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QHeaderView)

from core import i18n
from core.plc import reg_map_rows, get_tags
from ui.tag_editor import TagEditorDialog


class PlcPanel(QWidget):
    connect_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        box = QGroupBox(i18n.tr("plc.title"))
        g = QGridLayout(box)

        g.addWidget(QLabel(i18n.tr("plc.proto")), 0, 0)
        self.cmb_proto = QComboBox()
        self.cmb_proto.addItem("Modbus TCP", "tcp")
        self.cmb_proto.addItem("Modbus RTU", "rtu")
        self.cmb_proto.addItem("Snap7 (S7)", "s7")
        g.addWidget(self.cmb_proto, 0, 1)

        self.lb_host = QLabel(i18n.tr("plc.host"))
        self.ed_host = QLineEdit(self.cfg["plc"].get("host", "192.168.0.10"))
        g.addWidget(self.lb_host, 1, 0)
        g.addWidget(self.ed_host, 1, 1)
        self.lb_port = QLabel(i18n.tr("plc.port"))
        self.sp_port = QSpinBox()
        self.sp_port.setRange(1, 65535)
        self.sp_port.setValue(int(self.cfg["plc"].get("port", 502)))
        g.addWidget(self.lb_port, 2, 0)
        g.addWidget(self.sp_port, 2, 1)
        self.lb_rack = QLabel(i18n.tr("plc.rack"))
        self.sp_rack = QSpinBox()
        self.sp_rack.setRange(0, 7)
        self.sp_rack.setValue(int(self.cfg["plc"].get("rack", 0)))
        g.addWidget(self.lb_rack, 2, 2)
        g.addWidget(self.sp_rack, 2, 3)
        self.lb_slot = QLabel(i18n.tr("plc.slot"))
        self.sp_slot = QSpinBox()
        self.sp_slot.setRange(0, 31)
        self.sp_slot.setValue(int(self.cfg["plc"].get("slot", 1)))
        g.addWidget(self.lb_slot, 3, 2)
        g.addWidget(self.sp_slot, 3, 3)
        self.lb_db = QLabel(i18n.tr("plc.db"))
        self.sp_db = QSpinBox()
        self.sp_db.setRange(1, 65535)
        self.sp_db.setValue(int(self.cfg["plc"].get("db", 100)))
        g.addWidget(self.lb_db, 4, 2)
        g.addWidget(self.sp_db, 4, 3)

        self.lb_com = QLabel(i18n.tr("plc.com"))
        self.ed_com = QLineEdit(self.cfg["plc"].get("com", "COM3"))
        g.addWidget(self.lb_com, 3, 0)
        g.addWidget(self.ed_com, 3, 1)
        self.lb_baud = QLabel(i18n.tr("plc.baud"))
        self.cmb_baud = QComboBox()
        for b in (4800, 9600, 19200, 38400, 57600, 115200):
            self.cmb_baud.addItem(str(b), b)
        self.cmb_baud.setCurrentIndex(1)
        g.addWidget(self.lb_baud, 4, 0)
        g.addWidget(self.cmb_baud, 4, 1)

        self.lb_slave = QLabel(i18n.tr("plc.slave"))
        g.addWidget(self.lb_slave, 0, 2)
        self.sp_slave = QSpinBox()
        self.sp_slave.setRange(1, 247)
        self.sp_slave.setValue(int(self.cfg["plc"].get("slave", 1)))
        g.addWidget(self.sp_slave, 0, 3)
        self.lb_layout = QLabel(i18n.tr("plc.layout"))
        self.cmb_layout = QComboBox()
        self.cmb_layout.addItem(i18n.tr("plc.layout.grad"), "grad")
        self.cmb_layout.addItem(i18n.tr("plc.layout.block"), "block")
        _li = self.cmb_layout.findData(self.cfg["plc"].get("s7_layout", "grad"))
        self.cmb_layout.setCurrentIndex(max(0, _li))
        g.addWidget(self.lb_layout, 0, 2)
        g.addWidget(self.cmb_layout, 0, 3)
        g.addWidget(QLabel(i18n.tr("plc.interval")), 1, 2)
        self.sp_interval = QSpinBox()
        self.sp_interval.setRange(100, 5000)
        self.sp_interval.setSingleStep(100)
        self.sp_interval.setValue(int(self.cfg["plc"].get("interval", 500)))
        g.addWidget(self.sp_interval, 1, 3)

        row = QHBoxLayout()
        self.btn_conn = QPushButton(i18n.tr("plc.connect"))
        self.btn_disc = QPushButton(i18n.tr("plc.disconnect"))
        self.btn_disc.setEnabled(False)
        self.btn_conn.clicked.connect(self.connect_requested.emit)
        self.btn_disc.clicked.connect(self.disconnect_requested.emit)
        self.lb_status = QLabel(i18n.tr("plc.disconnected"))
        self.lb_status.setStyleSheet("color:#ff8a5c; font-weight:bold;")
        self.lb_status.setWordWrap(True)
        self.lb_status.setMinimumHeight(34)
        self.lb_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.addWidget(self.btn_conn)
        row.addWidget(self.btn_disc)
        self.btn_tags = QPushButton(i18n.tr("plc.tagedit.btn"))
        self.btn_tags.clicked.connect(self._edit_tags)
        row.addWidget(self.btn_tags)
        row.addStretch(1)
        row.addWidget(self.lb_status)
        g.addLayout(row, 5, 0, 1, 4)
        self.lb_hint = QLabel(i18n.tr("plc.layout.hint"))
        self.lb_hint.setStyleSheet("color:#7fa8d8; font-size:11px;")
        self.lb_hint.setWordWrap(True)
        g.addWidget(self.lb_hint, 6, 0, 1, 4)
        lay.addWidget(box)

        # 寄存器映射表
        box2 = QGroupBox(i18n.tr("plc.map"))
        v2 = QVBoxLayout(box2)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            i18n.tr("plc.tag"), i18n.tr("plc.desc"), i18n.tr("plc.reg"),
            i18n.tr("plc.scale"), i18n.tr("plc.rw"), i18n.tr("plc.value")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row_data in reg_map_rows():
            dev_id, desc, reg, scale, rw, field = row_data
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate([dev_id, desc, str(reg), str(scale), rw, "-"]):
                item = QTableWidgetItem(val)
                if c == 1:
                    item.setData(Qt.UserRole, field)   # 描述列附带字段名, 供精确匹配
                self.table.setItem(r, c, item)
        v2.addWidget(self.table)
        lay.addWidget(box2, 1)

        self.cmb_proto.currentIndexChanged.connect(self._proto_changed)
        self.cmb_layout.currentIndexChanged.connect(self._proto_changed)
        self._proto_changed()

    def _rebuild_table(self):
        """按当前协议/布局重建映射表"""
        proto = self.cmb_proto.currentData()
        if proto == "s7":
            grad = self.cmb_layout.currentData() == "grad"
            kind = "grad" if grad else "s7"
            tags = self.cfg["plc"].get("tags") if grad else None
        else:
            kind = "modbus"
            tags = None
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for row_data in reg_map_rows(kind, tags):
            dev_id, desc, reg, scale, rw, field = row_data
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate([dev_id, desc, str(reg), str(scale), rw, "-"]):
                item = QTableWidgetItem(val)
                if c == 1:
                    item.setData(Qt.UserRole, field)
                self.table.setItem(r, c, item)

    def _proto_changed(self):
        proto = self.cmb_proto.currentData()
        tcp = proto == "tcp"
        s7 = proto == "s7"
        grad = s7 and self.cmb_layout.currentData() == "grad"
        for w in (self.lb_host, self.ed_host):
            w.setVisible(tcp or s7)
        for w in (self.lb_port, self.sp_port):
            w.setVisible(tcp)
        # 布局/机架/插槽: 所有 S7 模式; DB号: 仅连续寄存器布局
        for w in (self.lb_rack, self.sp_rack, self.lb_slot, self.sp_slot,
                  self.lb_layout, self.cmb_layout, self.lb_hint):
            w.setVisible(s7)
        self.btn_tags.setVisible(s7 and grad)
        for w in (self.lb_db, self.sp_db):
            w.setVisible(s7 and not grad)
        for w in (self.lb_com, self.ed_com, self.lb_baud, self.cmb_baud):
            w.setVisible(proto == "rtu")
        for w in (self.lb_slave, self.sp_slave):
            w.setVisible(not s7)
        self._rebuild_table()

    def _edit_tags(self):
        dlg = TagEditorDialog(get_tags(self.cfg), self)
        if dlg.exec() == TagEditorDialog.Accepted:
            self.cfg["plc"]["tags"] = dlg.tags
            self._rebuild_table()

    def apply_to_cfg(self):
        self.cfg["plc"]["proto"] = self.cmb_proto.currentData()
        self.cfg["plc"]["host"] = self.ed_host.text().strip()
        self.cfg["plc"]["port"] = self.sp_port.value()
        self.cfg["plc"]["rack"] = self.sp_rack.value()
        self.cfg["plc"]["slot"] = self.sp_slot.value()
        self.cfg["plc"]["db"] = self.sp_db.value()
        self.cfg["plc"]["s7_layout"] = self.cmb_layout.currentData()
        self.cfg["plc"]["com"] = self.ed_com.text().strip()
        self.cfg["plc"]["baud"] = self.cmb_baud.currentData()
        self.cfg["plc"]["slave"] = self.sp_slave.value()
        self.cfg["plc"]["interval"] = self.sp_interval.value()

    def set_connected(self, connected):
        self.btn_conn.setEnabled(not connected)
        self.btn_disc.setEnabled(connected)
        self.lb_status.setText(i18n.tr("plc.connected") if connected
                               else i18n.tr("plc.disconnected"))
        self.lb_status.setStyleSheet(
            "color:#6fe08a; font-weight:bold;" if connected
            else "color:#ff8a5c; font-weight:bold;")

    def set_status(self, text):
        self.lb_status.setText(text)

    def update_values(self, states):
        """states: {dev_id: {field: value}} -> 按设备+字段精确刷新表内当前值"""
        for dev_id, item in states.items():
            for field, val in item.items():
                # 在表中查找该设备该字段行 (字段名在描述列 UserRole, 避免"温度"
                # 误匹配"温度设定")
                for r in range(self.table.rowCount()):
                    it_dev = self.table.item(r, 0)
                    it_desc = self.table.item(r, 1)
                    if (it_dev is not None and it_dev.text() == dev_id
                            and it_desc is not None
                            and it_desc.data(Qt.UserRole) == field):
                        self.table.setItem(r, 5, QTableWidgetItem(f"{val}"))
                        break

    def retranslate(self):
        self.setWindowTitle(i18n.tr("plc.title"))
