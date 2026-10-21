# -*- coding: utf-8 -*-
"""设备调节弹窗: 实时数据 + 手动输入开度/转速 + AI 本地模型建议"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QSlider, QSpinBox, QDoubleSpinBox,
                               QPushButton, QTextEdit, QGroupBox, QCheckBox,
                               QWidget, QAbstractSlider, QAbstractSpinBox)

from core import i18n

# 设定值字段: (字段名, 显示名 i18n key, 下限, 上限, 单位)
SP_SPECS = [("sp_temp", "field.sp_temp", -50.0, 500.0, "℃"),
            ("sp_level", "field.sp_level", 0.0, 100.0, "%")]


class DeviceDialog(QDialog):
    def __init__(self, st, dev_id, advisor, apply_action,
                 loop_mgr=None, sp_fields=None, parent=None):
        super().__init__(parent)
        self.st = st
        self.dev_id = dev_id
        self.dev = st.devices[dev_id]
        self.advisor = advisor
        self.apply_action = apply_action
        self.loop_mgr = loop_mgr
        # {sp_field: 是否可写} —— 点表中为该设备配置了对应 sp_* 点时才有
        self.sp_fields = dict(sp_fields or {})
        self._loop_rows = (loop_mgr.loops_for_device(dev_id)
                           if loop_mgr is not None else [])
        self._token = ("dialog", dev_id, id(self))
        self._waiting = False
        self._dirty_valve = False    # 用户已拖动/输入但尚未点应用
        self._dirty_speed = False
        self._dirty_power = False
        self._dirty_sp = {}          # sp_field -> True 已改未应用
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(f"{dev_id} {i18n.tr(dev_id)} - {i18n.tr('dlg.manual')}")
        self.setMinimumWidth(380)
        self._build()
        self._refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(500)
        if advisor is not None:
            advisor.suggestions_ready.connect(self._on_ai)
            self._request_ai()
        self.destroyed.connect(self._cleanup)

    # ---------- UI ----------
    def _build(self):
        lay = QVBoxLayout(self)
        dtype = self.dev.dtype
        info = QGroupBox(i18n.tr("field.state") + " / " + i18n.tr("app.title").split(" ")[0])
        info.setTitle(i18n.tr("field.state"))
        form = QFormLayout(info)

        def lab():
            l = QLabel()
            form.addRow("", l)
            return l

        self.l_temp = lab()
        self.l_press = lab()
        # 塔器: T101温度即塔顶温度
        form.addRow(f"<b>{i18n.tr('field.top_temp' if dtype == 'column' else 'field.temp')}</b>",
                    self.l_temp)
        form.addRow(f"<b>{i18n.tr('field.press')}</b>", self.l_press)
        if dtype in ("tank",):
            self.l_level = lab()
            form.addRow(f"<b>{i18n.tr('field.level')}</b>", self.l_level)
        if dtype == "column":
            # 塔釜温度 = E102温度
            self.l_bot = lab()
            form.addRow(f"<b>{i18n.tr('field.bot_temp')}</b>", self.l_bot)
        if dtype in ("valve", "pump"):
            self.l_open = lab()
            form.addRow(f"<b>{i18n.tr('field.opening')}</b>", self.l_open)
        if dtype == "pump":
            self.l_speed = lab()
            self.l_run = lab()
            form.addRow(f"<b>{i18n.tr('field.speed')}</b>", self.l_speed)
            form.addRow(f"<b>{i18n.tr('field.running')}</b>", self.l_run)
        if dtype == "exchanger":
            self.l_power = lab()
            form.addRow(f"<b>{i18n.tr('field.power')}</b>", self.l_power)
        # PLC 设定值 (点表配置了 sp_temp/sp_level 时显示, 未读到值显示 --)
        self.l_sp = {}
        for f, key, _lo, _hi, unit in SP_SPECS:
            if f in self.sp_fields:
                l = lab()
                form.addRow(f"<b>{i18n.tr(key)}</b>", l)
                self.l_sp[f] = (l, unit)
        lay.addWidget(info)

        # ---- 手动调节 ----
        ctrl = self.manual_group = QGroupBox(i18n.tr("dlg.manual"))
        cv = QVBoxLayout(ctrl)
        if dtype == "valve":
            cv.addWidget(QLabel(f"{i18n.tr('field.opening')} (0-100%)"))
            row = QHBoxLayout()
            self.sl = QSlider(Qt.Horizontal)
            self.sl.setRange(0, 100)
            self.sp = QSpinBox()
            self.sp.setRange(0, 100)
            self.sl.valueChanged.connect(self.sp.setValue)
            self.sp.valueChanged.connect(self._on_valve_spin)
            btn = QPushButton(i18n.tr("dlg.apply"))
            btn.clicked.connect(self._apply_valve)
            row.addWidget(self.sl)
            row.addWidget(self.sp)
            row.addWidget(btn)
            cv.addLayout(row)
        elif dtype == "pump":
            row = QHBoxLayout()
            self.cb_run = QCheckBox(i18n.tr("field.running"))
            self.cb_run.setEnabled(False)   # 纯状态指示, 启停由按钮操作
            btn_on = QPushButton(i18n.tr("dlg.start"))
            btn_off = QPushButton(i18n.tr("dlg.stop"))
            btn_on.clicked.connect(lambda: self.apply_action(
                {"device": self.dev_id, "param": "running", "value": 1}))
            btn_off.clicked.connect(lambda: self.apply_action(
                {"device": self.dev_id, "param": "running", "value": 0}))
            row.addWidget(self.cb_run)
            row.addWidget(btn_on)
            row.addWidget(btn_off)
            cv.addLayout(row)
            row2 = QHBoxLayout()
            row2.addWidget(QLabel(f"{i18n.tr('field.speed')} (0-100%)"))
            self.sp_speed = QSpinBox()
            self.sp_speed.setRange(0, 100)
            self.sp_speed.valueChanged.connect(
                lambda: setattr(self, "_dirty_speed", True))
            b2 = QPushButton(i18n.tr("dlg.apply"))
            b2.clicked.connect(self._apply_speed)
            row2.addWidget(self.sp_speed)
            row2.addWidget(b2)
            cv.addLayout(row2)
        elif dtype == "exchanger":
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{i18n.tr('field.power')} (0-100%)"))
            self.sp_power = QSpinBox()
            self.sp_power.setRange(0, 100)
            self.sp_power.valueChanged.connect(
                lambda: setattr(self, "_dirty_power", True))
            b = QPushButton(i18n.tr("dlg.apply"))
            b.clicked.connect(self._apply_power)
            row.addWidget(self.sp_power)
            row.addWidget(b)
            cv.addLayout(row)
        else:   # tank / column 默认只读 (若有点表可写设定值, 下面追加输入行)
            if not any(self.sp_fields.values()):
                cv.addWidget(QLabel("—" if i18n.get_lang() == "en"
                                    else "储罐/塔为监视设备, 无可调开度"))
        # ---- PLC 设定值下发 (点表中该 sp 点为 R/W 时) ----
        self.sp_sp = {}
        for f, key, lo, hi, unit in SP_SPECS:
            if not self.sp_fields.get(f):
                continue
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{i18n.tr(key)} ({lo:g}~{hi:g}{unit})"))
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setDecimals(1)
            sp.setSuffix(f" {unit}")
            sp.valueChanged.connect(
                lambda _=None, ff=f: self._dirty_sp.__setitem__(ff, True))
            btn = QPushButton(i18n.tr("dlg.apply"))
            btn.clicked.connect(lambda _=False, ff=f: self._apply_sp(ff))
            row.addWidget(sp)
            row.addWidget(btn)
            cv.addLayout(row)
            self.sp_sp[f] = sp
        lay.addWidget(ctrl)

        # ---- PID 自动控制 (该设备作为某回路执行器时显示) ----
        self._manual_inputs = self._collect_manual_inputs()
        if self._loop_rows:
            auto_box = QGroupBox(i18n.tr("dlg.auto_ctrl"))
            av2 = QVBoxLayout(auto_box)
            self.lb_loop_info = QLabel()
            self.lb_loop_info.setWordWrap(True)
            self.lb_loop_info.setStyleSheet("color:#0d47a1; font-weight:600;")
            av2.addWidget(self.lb_loop_info)
            self.cb_loop_auto = QCheckBox(i18n.tr("dlg.loop_auto"))
            self.cb_loop_auto.toggled.connect(self._toggle_loop_auto)
            av2.addWidget(self.cb_loop_auto)
            lb_note = QLabel(i18n.tr("dlg.loop_note"))
            lb_note.setWordWrap(True)
            lb_note.setStyleSheet("color:#666666; font-size:11px;")
            av2.addWidget(lb_note)
            lay.addWidget(auto_box)

        # ---- AI 建议 ----
        ai = QGroupBox(i18n.tr("dlg.ai_advice"))
        av = QVBoxLayout(ai)
        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setMinimumHeight(120)
        self.ai_text.setPlaceholderText(i18n.tr("dlg.no_ai"))
        av.addWidget(self.ai_text)
        arow = QHBoxLayout()
        b_refresh = QPushButton(i18n.tr("dlg.refresh"))
        b_refresh.clicked.connect(self._request_ai)
        b_apply = QPushButton(i18n.tr("dlg.apply_ai"))
        b_apply.clicked.connect(self._apply_ai)
        arow.addWidget(b_refresh)
        arow.addWidget(b_apply)
        av.addLayout(arow)
        lay.addWidget(ai)

    # ---------- 手动应用 (应用后解除 dirty, 控件恢复与设备值同步) ----------
    def _on_valve_spin(self, v):
        self.sl.setValue(v)
        self._dirty_valve = True

    def _apply_valve(self):
        self.apply_action({"device": self.dev_id, "param": "opening",
                           "value": float(self.sp.value())})
        self._dirty_valve = False

    def _apply_speed(self):
        self.apply_action({"device": self.dev_id, "param": "speed",
                           "value": float(self.sp_speed.value())})
        self._dirty_speed = False

    def _apply_power(self):
        self.apply_action({"device": self.dev_id, "param": "power",
                           "value": float(self.sp_power.value())})
        self._dirty_power = False

    def _apply_sp(self, field):
        sp = self.sp_sp.get(field)
        if sp is None:
            return
        self.apply_action({"device": self.dev_id, "param": field,
                           "value": float(sp.value())})
        self._dirty_sp[field] = False

    # ---------- PID 手自动 ----------
    def _collect_manual_inputs(self):
        ws = []
        for cls in (QAbstractSlider, QAbstractSpinBox, QPushButton):
            ws.extend(self.manual_group.findChildren(cls))
        return ws

    def _toggle_loop_auto(self, on):
        if not self._loop_rows:
            return
        lid, row = self._loop_rows[0]
        cur_mv = float(getattr(self.dev, row["mv_param"]))
        self.loop_mgr.set_auto(lid, on, current_mv=cur_mv)
        for w in self._manual_inputs:
            w.setEnabled(not on)
        self.st.log_event("pid.auto_on" if on else "pid.auto_off",
                          dev=self.dev_id, loop=i18n.tr(row["name"]))

    # ---------- 刷新 ----------
    def _refresh(self):
        d = self.dev
        dt = self.dev.dtype
        self.l_temp.setText(f"{d.temp:.1f} ℃")
        self.l_press.setText(f"{d.press:.1f} kPa")
        if dt == "tank":
            self.l_level.setText(f"{d.level:.1f} %")
        if dt == "column":
            e102 = self.st.devices.get("E102")
            bot = e102.temp if e102 is not None else d.temp
            self.l_bot.setText(f"{bot:.1f} ℃")
        if dt in ("valve", "pump"):
            self.l_open.setText(f"{d.opening:.1f} %")
        if dt == "pump":
            self.l_speed.setText(f"{d.speed:.1f} %")
            self.l_run.setText(i18n.tr("state.on") if d.running else i18n.tr("state.off"))
            if hasattr(self, "cb_run"):
                self.cb_run.setChecked(d.running)
        if dt == "exchanger":
            self.l_power.setText(f"{d.power:.1f} %")
            if hasattr(self, "sp_power") and not self.sp_power.hasFocus() \
                    and not self._dirty_power:
                self.sp_power.setValue(int(d.power))
        # PLC 设定值: 状态行 + 输入框回读 (未读到/未配置显示 --)
        for f, (l, unit) in self.l_sp.items():
            v = getattr(d, f, None)
            l.setText("--" if v is None else f"{float(v):.1f} {unit}")
            sp = self.sp_sp.get(f)
            if sp is not None and v is not None and not sp.hasFocus() \
                    and not self._dirty_sp.get(f):
                sp.blockSignals(True)
                sp.setValue(float(v))
                sp.blockSignals(False)
        if dt == "valve" and hasattr(self, "sp") and not self.sp.hasFocus() \
                and not self.sl.isSliderDown() and not self._dirty_valve:
            self.sp.setValue(int(d.opening))
        if dt == "pump" and hasattr(self, "sp_speed") and not self.sp_speed.hasFocus() \
                and not self._dirty_speed:
            self.sp_speed.setValue(int(d.speed))
        if d.alarms:
            alarm_txt = "; ".join(f"{i18n.tr(k)} {v}" for k, v in d.alarms)
            self.setWindowTitle(f"⚠ {self.dev_id} {i18n.tr(self.dev_id)} - {alarm_txt}")
        # PID 回路状态行
        if self._loop_rows:
            lid, row = self._loop_rows[0]
            pv = self.loop_mgr._pv(self.st, row)
            sp = self.loop_mgr._setpoint(self.st, row)
            mv = float(getattr(d, row["mv_param"]))
            mode = i18n.tr("loop.mode.auto") if row["auto"] \
                else i18n.tr("loop.mode.manual")
            pv_txt = f"{pv:.1f}" if pv is not None else "--"
            self.lb_loop_info.setText(
                f"{i18n.tr(row['name'])}    "
                f"SP {sp:.1f} / PV {pv_txt} / {i18n.tr('dlg.cur_out')} {mv:.1f}%    [{mode}]")
            self.cb_loop_auto.blockSignals(True)
            self.cb_loop_auto.setChecked(bool(row["auto"]))
            self.cb_loop_auto.blockSignals(False)
            for w in self._manual_inputs:
                w.setEnabled(not row["auto"])

    # ---------- AI ----------
    def _request_ai(self):
        if self.advisor is None:
            return
        self._waiting = True
        self.ai_text.setPlainText(i18n.tr("dlg.thinking"))
        self.advisor.request_analysis(self.dev_id, token=self._token)

    def _on_ai(self, actions, text, token):
        if token != self._token or not self._waiting:
            return
        self._waiting = False
        self.ai_text.setPlainText(text or i18n.tr("ai.none"))
        self._last_actions = [a for a in actions if a["device"] == self.dev_id]

    def _apply_ai(self):
        for a in getattr(self, "_last_actions", []):
            self.apply_action(a, "ai")

    def _cleanup(self):
        try:
            if self.advisor is not None:
                self.advisor.suggestions_ready.disconnect(self._on_ai)
        except Exception:
            pass
