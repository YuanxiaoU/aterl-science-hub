# -*- coding: utf-8 -*-
"""底部右侧模块: 活动报警汇总 + 关键工艺参数实时监视"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QListWidget, QListWidgetItem, QGridLayout,
                               QLabel)

from core import i18n

# (设备, 字段, 名称词条, 单位, 报警判断函数)
def _press_alarm(v):
    return v > 125.0 or v < 96.0

def _lvl_alarm(v):
    return v > 90.0 or v < 10.0

def _temp_top_alarm(v):
    return v > 95.0

def _temp_bot_alarm(v):
    return v > 108.0

KEY_ITEMS = [
    ("T101", "temp", "field.top_temp", "unit.c", _temp_top_alarm),
    ("E102", "temp", "field.bot_temp", "unit.c", _temp_bot_alarm),
    ("T101", "press", "field.press", "unit.kpa", _press_alarm),
    ("V101", "level", "field.level", "unit.pct", _lvl_alarm),
    ("V102", "level", "field.level", "unit.pct", _lvl_alarm),
    ("V103", "level", "field.level", "unit.pct", _lvl_alarm),
    ("V104", "level", "field.level", "unit.pct", _lvl_alarm),
]

COL_NORMAL = "#d8e2ee"
COL_ALARM = "#ff6a6a"
COL_OK = "#6fe08a"


class AlarmPanel(QWidget):
    def __init__(self, st, parent=None):
        super().__init__(parent)
        self.st = st
        self._value_labels = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)

        # ---- 活动报警 ----
        gb1 = QGroupBox(i18n.tr("alarm.active"))
        v1 = QVBoxLayout(gb1)
        self.alarm_list = QListWidget()
        self.alarm_list.setStyleSheet("QListWidget{background:#10161e; border:none;}")
        v1.addWidget(self.alarm_list)
        lay.addWidget(gb1, 3)

        # ---- 关键参数 ----
        gb2 = QGroupBox(i18n.tr("key.indicators"))
        grid = QGridLayout(gb2)
        grid.setContentsMargins(8, 14, 8, 8)
        for r, (dev, field, name_key, unit_key, _) in enumerate(KEY_ITEMS):
            title = f"{dev} {i18n.tr(name_key)}"
            grid.addWidget(QLabel(title), r, 0)
            lb = QLabel("--")
            lb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lb.setMinimumWidth(96)
            grid.addWidget(lb, r, 1)
            self._value_labels[(dev, field)] = (lb, unit_key, KEY_ITEMS[r][4])
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        lay.addWidget(gb2, 2)

    def update_panel(self):
        st = self.st
        # 报警列表
        self.alarm_list.clear()
        any_alarm = False
        for dev_id, lst in st.active_alarms.items():
            for key, val in lst:
                any_alarm = True
                msg = i18n.tr(key)
                if val not in (None, ""):
                    msg += f"  ({val})" if isinstance(val, str) else f"  {val:.1f}"
                it = QListWidgetItem(f"● [{dev_id}] {msg}")
                it.setForeground(Qt.red)
                self.alarm_list.addItem(it)
        if not any_alarm:
            it = QListWidgetItem(i18n.tr("alarm.none"))
            it.setForeground(Qt.darkGreen)
            self.alarm_list.addItem(it)
        # 关键参数
        for (dev_id, field), (lb, unit_key, alarm_fn) in self._value_labels.items():
            dev = st.devices.get(dev_id)
            if dev is None:
                continue
            v = getattr(dev, field, None)
            if v is None:
                continue
            lb.setText(f"{v:.1f} {i18n.tr(unit_key)}")
            alarmed = bool(dev.alarms) or alarm_fn(v)
            lb.setStyleSheet(f"color:{COL_ALARM}; font-weight:bold;" if alarmed
                             else f"color:{COL_NORMAL};")
