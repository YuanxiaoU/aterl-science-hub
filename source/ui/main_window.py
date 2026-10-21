# -*- coding: utf-8 -*-
"""主窗口: 菜单栏 / DCS页 / 趋势页 / 停靠面板 / 模式切换 / 定时循环"""
import os
import time

from PySide6.QtCore import Qt, QTimer, QEvent, QRect
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPixmap, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QComboBox, QTabWidget,
                               QScrollArea, QDockWidget, QListWidget, QFileDialog,
                               QMessageBox, QStackedWidget, QGroupBox, QDialog)

from core import i18n
from core.config import load_config, save_config
from core.app_state import AppState
from core.materials import all_materials, find_material
from core.simulation import SimulationEngine, compute_flows
from core.ai_advisor import AIAdvisor
from core.plc import PLCWorker, get_tags
from core.data_logger import DataLogger, format_event
from core.loops import LoopManager
from core.case_store import CaseStore

from ui.dcs_canvas import DcsCanvas
from ui.device_dialog import DeviceDialog
from ui.trend_view import TrendView
from ui.plc_panel import PlcPanel
from ui.material_panel import MaterialPanel
from ui.ai_dock import AiDock
from ui.alarm_panel import AlarmPanel
from ui.metrics_chart import MetricsChart
from ui.loop_dialog import LoopDialog

FIT_FLOOR_Z = 0.85   # 适应窗口时缩放下限, 保证图内文字可读 (空间不足则出现滚动条)

SPEED_OPTIONS = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]   # 运行速度档位


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        i18n.set_lang(self.cfg.get("language", "zh"))
        self.st = AppState()
        self.st.material = find_material("乙醇-水体系")
        self.engine = SimulationEngine(self.st)
        self.engine.reset()
        self.advisor = AIAdvisor(self.st, self.cfg)
        self.logger = DataLogger()
        self.loop_mgr = LoopManager(self.cfg)
        self.case_store = CaseStore()
        self.advisor.case_store = self.case_store
        self.plc_worker = None
        self._dialogs = {}
        self._acc = 0.0            # 仿真采样累计
        self._log_acc = 0.0
        self._ai_acc = 0.0
        self._plc_acc = 0.0
        self._pid_case_acc = {}    # lid -> 上次记录 PID 案例的仿真时刻 (节流)
        self._event_idx = 0
        self._focus = False
        self._build_ui()
        self.advisor.check()
        self.advisor.status_changed.connect(
            lambda on, msg: self.lb_ai.setText(("AI: " if i18n.get_lang() == "zh" else "AI: ") + msg))

        self.loop = QTimer(self)
        self.loop.timeout.connect(self._on_loop)
        self.loop.start(200)
        # 窗口显示后执行一次整图适应
        QTimer.singleShot(0, lambda: self._apply_fit() if self._auto_fit else None)

    # ================= UI 构建 =================
    def _build_ui(self):
        self.setWindowTitle(i18n.tr("app.title"))
        self.resize(1680, 980)
        # 窗口图标 (内嵌资源)
        try:
            from ui.logo_asset import logo_png_bytes
            _pm = QPixmap()
            _pm.loadFromData(logo_png_bytes())
            if not _pm.isNull():
                self.setWindowIcon(QIcon(_pm))
        except Exception:
            pass
        self._build_menus()
        self._build_central()
        self._build_docks()
        self._build_statusbar()
        # 仅首次构建时恢复窗口尺寸/布局 (语言切换重建不重置)
        if not getattr(self, "_geom_restored", False):
            self._restore_geometry()
            self._geom_restored = True

    def _build_menus(self):
        mb = self.menuBar()
        mb.clear()
        # 系统
        m_sys = mb.addMenu(i18n.tr("menu.system"))
        act_log = QAction(i18n.tr("act.export_log"), self)
        act_log.triggered.connect(self.export_log)
        m_sys.addAction(act_log)
        act_clr = QAction(i18n.tr("act.clear_trend"), self)
        act_clr.triggered.connect(self._clear_trend)
        m_sys.addAction(act_clr)
        act_cases = QAction(i18n.tr("act.export_cases"), self)
        act_cases.triggered.connect(self.export_cases)
        m_sys.addAction(act_cases)
        m_sys.addSeparator()
        act_quit = QAction(i18n.tr("act.exit"), self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        m_sys.addAction(act_quit)
        # 视图
        m_view = mb.addMenu(i18n.tr("menu.view"))
        self.act_focus = QAction(i18n.tr("act.focus"), self, checkable=True)
        self.act_focus.setShortcut(QKeySequence("F11"))
        self.act_focus.toggled.connect(self._toggle_focus)
        m_view.addAction(self.act_focus)
        act_loops = QAction(i18n.tr("btn.loops"), self)
        act_loops.triggered.connect(self._open_loops)
        m_view.addAction(act_loops)
        # 模式
        m_mode = mb.addMenu(i18n.tr("menu.mode"))
        grp = QActionGroup(self)
        self.act_sim = QAction(i18n.tr("mode.sim"), self, checkable=True)
        self.act_plc = QAction(i18n.tr("mode.plc"), self, checkable=True)
        grp.addAction(self.act_sim)
        grp.addAction(self.act_plc)
        self.act_sim.setChecked(self.st.mode == "sim")
        self.act_plc.setChecked(self.st.mode == "plc")
        self.act_sim.triggered.connect(lambda: self.set_mode("sim"))
        self.act_plc.triggered.connect(lambda: self.set_mode("plc"))
        m_mode.addAction(self.act_sim)
        m_mode.addAction(self.act_plc)
        # 语言
        m_lang = mb.addMenu(i18n.tr("menu.language"))
        grp2 = QActionGroup(self)
        self.act_zh = QAction(i18n.tr("lang.zh"), self, checkable=True)
        self.act_en = QAction(i18n.tr("lang.en"), self, checkable=True)
        grp2.addAction(self.act_zh)
        grp2.addAction(self.act_en)
        self.act_zh.setChecked(i18n.get_lang() == "zh")
        self.act_en.setChecked(i18n.get_lang() == "en")
        self.act_zh.triggered.connect(lambda: self.apply_language("zh"))
        self.act_en.triggered.connect(lambda: self.apply_language("en"))
        m_lang.addAction(self.act_zh)
        m_lang.addAction(self.act_en)
        # 帮助
        m_help = mb.addMenu(i18n.tr("menu.help"))
        act_about = QAction(i18n.tr("act.about"), self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)

    def _show_about(self):
        """关于对话框: 展示 logo + 版本/功能说明"""
        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.tr("act.about"))
        dlg.setFixedSize(460, 320)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        top = QHBoxLayout(); top.setSpacing(16)
        # logo
        lb_logo = QLabel()
        pm = QPixmap()
        try:
            from ui.logo_asset import logo_png_bytes
            pm.loadFromData(logo_png_bytes())
        except Exception:
            pass
        if not pm.isNull():
            lb_logo.setPixmap(pm.scaled(96, 96, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        lb_logo.setFixedSize(100, 100)
        lb_logo.setAlignment(Qt.AlignCenter)
        top.addWidget(lb_logo)
        title = QLabel("Aterl-DistSim")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #dceafc;")
        sub = QLabel(i18n.tr("app.title").replace("Aterl-DistSim", "").strip(" —-")
                     or "Distillation Simulation & Control")
        sub.setStyleSheet("color: #9fc0dd; font-size: 12px;")
        ver = QLabel("v1.0")
        ver.setStyleSheet("color: #6fb6ea; font-size: 12px;")
        tb = QVBoxLayout(); tb.setSpacing(4)
        tb.addStretch(1); tb.addWidget(title); tb.addWidget(sub); tb.addWidget(ver)
        tb.addStretch(1)
        top.addLayout(tb, 1)
        lay.addLayout(top)
        body = QLabel(i18n.tr("about.text").split("\n\n", 1)[-1])
        body.setWordWrap(True)
        body.setStyleSheet("color: #c7d6e8; font-size: 12px;")
        lay.addWidget(body, 1)
        btn = QPushButton(i18n.tr("confirm"))
        btn.setFixedWidth(110)
        btn.clicked.connect(dlg.accept)
        bb = QHBoxLayout(); bb.addStretch(1); bb.addWidget(btn); bb.addStretch(1)
        lay.addLayout(bb)
        dlg.exec()

    def _build_central(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # ---- DCS 页 ----
        page_dcs = QWidget()
        v = QVBoxLayout(page_dcs)
        v.setContentsMargins(4, 4, 4, 4)
        # 工具条: 运行/暂停/重置/速度
        bar = QHBoxLayout()
        self.btn_run = QPushButton("▶ " + i18n.tr("sim.run"))
        self.btn_run.setCheckable(True)
        self.btn_run.setChecked(self.st.running)
        self.btn_run.toggled.connect(self._toggle_run)
        self.btn_reset = QPushButton(i18n.tr("sim.reset"))
        self.btn_reset.clicked.connect(self._reset_sim)
        self.lb_speed = QLabel(i18n.tr("sim.speed") + ":")
        self.cb_speed = QComboBox()
        for f in SPEED_OPTIONS:
            self.cb_speed.addItem(f"×{f:g}", f)
        self.cb_speed.setCurrentIndex(SPEED_OPTIONS.index(1.0))   # 默认 ×1
        self.cb_speed.setFixedWidth(86)
        self.cb_speed.currentIndexChanged.connect(
            lambda _i: self._on_speed(self.cb_speed.currentData()))
        self.st.speed = 1.0
        bar.addWidget(self.btn_run)
        # 紧急停车 (ESD): 立即关闭全部阀门、停泵、切加热
        self.btn_esd = QPushButton("■ " + i18n.tr("sim.esd"))
        self.btn_esd.setStyleSheet(
            "QPushButton{background:#8a1f1f; border:1px solid #c04040; color:#ffd9d9;"
            " font-weight:bold; padding:5px 14px;}"
            "QPushButton:hover{background:#a82828;}"
            "QPushButton:pressed{background:#6e1515;}")
        self.btn_esd.clicked.connect(self._esd)
        bar.addWidget(self.btn_esd)
        # ESD 复位按钮 (仅锁定时显示)
        self.btn_esd_reset = QPushButton("↻ ESD 复位")
        self.btn_esd_reset.setStyleSheet(
            "QPushButton{background:#1f5f8a; border:1px solid #4090c0; color:#d9efff;"
            " font-weight:bold; padding:5px 12px;}"
            "QPushButton:hover{background:#2878a8;}")
        self.btn_esd_reset.clicked.connect(self._esd_reset)
        self.btn_esd_reset.setVisible(False)
        bar.addWidget(self.btn_esd_reset)
        bar.addWidget(self.btn_reset)
        bar.addSpacing(16)
        bar.addWidget(self.lb_speed)
        bar.addWidget(self.cb_speed)
        bar.addSpacing(12)
        self.btn_loops = QPushButton(i18n.tr("btn.loops"))
        self.btn_loops.clicked.connect(self._open_loops)
        bar.addWidget(self.btn_loops)
        # 自动实验 (毕业设计数据采集)
        self.btn_exp = QPushButton("🧪 " + i18n.tr("btn.experiment"))
        self.btn_exp.setStyleSheet(
            "QPushButton{background:#1f5f8a; border:1px solid #4090c0; color:#d9efff;"
            " font-weight:bold; padding:5px 12px;}"
            "QPushButton:hover{background:#2878a8;}")
        self.btn_exp.clicked.connect(self._open_experiment)
        bar.addWidget(self.btn_exp)
        self.btn_focus = QPushButton("⛶ " + i18n.tr("btn.focus"))
        self.btn_focus.setCheckable(True)
        self.btn_focus.toggled.connect(self._toggle_focus)
        bar.addWidget(self.btn_focus)
        bar.addStretch(1)
        # 画布缩放: 适应窗口(默认, 整图全显) / 放大 / 缩小 / 100%
        self.btn_fit = QPushButton(i18n.tr("zoom.fit"))
        self.btn_fit.setCheckable(True)
        self.btn_fit.setChecked(True)
        self.btn_fit.clicked.connect(self._zoom_fit)
        self.btn_zout = QPushButton("－")
        self.btn_zout.setMaximumWidth(36)
        self.btn_zout.clicked.connect(lambda: self._zoom_manual(1 / 1.25))
        self.btn_zin = QPushButton("＋")
        self.btn_zin.setMaximumWidth(36)
        self.btn_zin.clicked.connect(lambda: self._zoom_manual(1.25))
        self.btn_actual = QPushButton("100%")
        self.btn_actual.setMaximumWidth(56)
        self.btn_actual.clicked.connect(self._zoom_actual)
        self.lb_zoom = QLabel("100%")
        self.lb_zoom.setMinimumWidth(48)
        bar.addWidget(self.btn_fit)
        bar.addWidget(self.btn_zout)
        bar.addWidget(self.lb_zoom)
        bar.addWidget(self.btn_zin)
        bar.addWidget(self.btn_actual)
        v.addLayout(bar)

        # ESD 红色横幅 (锁定时显示)
        self.esd_banner = QLabel("⚠ ESD 已触发")
        self.esd_banner.setStyleSheet(
            "QLabel{background:#c0392b; color:white; font-weight:bold;"
            " padding:6px; border:1px solid #922b21;}")
        self.esd_banner.setAlignment(Qt.AlignCenter)
        self.esd_banner.setVisible(False)
        v.addWidget(self.esd_banner)

        self.canvas = DcsCanvas(self.st)
        self.canvas.device_clicked.connect(self.open_device_dialog)
        self.sc = QScrollArea()
        self.sc.setWidget(self.canvas)
        self.sc.setAlignment(Qt.AlignCenter)
        self.sc.viewport().installEventFilter(self)
        self._auto_fit = True
        v.addWidget(self.sc, 1)
        self.tabs.addTab(page_dcs, i18n.tr("tab.dcs"))

        # ---- 趋势页 ----
        self.trend = TrendView(self.st)
        self.tabs.addTab(self.trend, i18n.tr("tab.trend"))
        self._update_controls()

    def _build_docks(self):
        # 左侧: 仿真页(物料体系 + 能耗生产图) / PLC 配置页
        self.left_stack = QStackedWidget()
        self.mat_panel = MaterialPanel(self.st)
        self.mat_panel.material_changed.connect(self._on_material)
        self.metrics = MetricsChart(self.st)

        sim_page = QWidget()
        self.sim_left_layout = QVBoxLayout(sim_page)
        self.sim_left_layout.setContentsMargins(1, 1, 1, 1)
        self.sim_left_layout.setSpacing(3)
        self.sim_left_layout.addWidget(self.mat_panel, 1)   # 物料体系 约1/3
        self.sim_left_layout.addWidget(self.metrics, 2)     # 能耗生产图 约2/3
        self._metrics_in_sim = True

        self.plc_panel = PlcPanel(self.cfg)
        self.plc_panel.connect_requested.connect(self._plc_connect)
        self.plc_panel.disconnect_requested.connect(self._plc_disconnect)
        self.left_stack.addWidget(sim_page)        # 0
        self.left_stack.addWidget(self.plc_panel)  # 1
        dock_l = QDockWidget("", self)
        dock_l.setObjectName("dockLeft")
        dock_l.setWidget(self.left_stack)
        dock_l.setFeatures(QDockWidget.DockWidgetMovable)
        dock_l.setTitleBarWidget(QWidget())   # 无标题栏, 内容贴边
        dock_l.setMinimumWidth(280)
        dock_l.setMaximumWidth(460)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_l)
        self.dock_left = dock_l

        # 右侧: AI
        self.ai_dock_w = AiDock(self.st, self.advisor, self.apply_action,
                               on_ignore=self._ignore_ai_action)
        dock_r = QDockWidget(i18n.tr("ai.dock_title"), self)
        dock_r.setObjectName("dockAI")
        dock_r.setWidget(self.ai_dock_w)
        dock_r.setFeatures(QDockWidget.DockWidgetMovable)
        dock_r.setMinimumWidth(280)
        dock_r.setMaximumWidth(420)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_r)
        self.dock_ai = dock_r

        # 底部: 事件日志(左) + [PLC模式: 能耗生产图] + 活动报警/关键参数(右)
        bottom = QWidget()
        self.bottom_layout = QHBoxLayout(bottom)
        self.bottom_layout.setContentsMargins(1, 1, 1, 1)
        self.bottom_layout.setSpacing(3)
        self.event_list = QListWidget()
        self.alarm_panel = AlarmPanel(self.st)
        self.bottom_layout.addWidget(self.event_list, 3)
        self.bottom_layout.addWidget(self.alarm_panel, 2)
        dock_b = QDockWidget(i18n.tr("dock.events"), self)
        dock_b.setObjectName("dockEvents")
        dock_b.setWidget(bottom)
        dock_b.setFeatures(QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock_b)
        self.dock_events = dock_b
        self._place_metrics()
        self._render_all_events()

    def _build_statusbar(self):
        self.lb_mode = QLabel()
        self.lb_simtime = QLabel()
        self.lb_ai = QLabel("AI: ...")
        self.lb_plc = QLabel()
        sb = self.statusBar()
        sb.addWidget(self.lb_mode)
        sb.addWidget(self.lb_simtime)
        sb.addPermanentWidget(self.lb_plc)
        sb.addPermanentWidget(self.lb_ai)
        self._update_statusbar()

    def _update_statusbar(self):
        mode_txt = i18n.tr("status.mode") + ": " + (
            i18n.tr("mode.sim") if self.st.mode == "sim" else i18n.tr("mode.plc"))
        self.lb_mode.setText(mode_txt)
        h, m, s = int(self.st.sim_time // 3600), int(self.st.sim_time % 3600 // 60), int(self.st.sim_time % 60)
        self.lb_simtime.setText(f"{i18n.tr('sim.time')}: {h:02d}:{m:02d}:{s:02d}")
        self.lb_plc.setText("PLC: " + (i18n.tr("plc.connected")
                            if self.plc_worker and self.plc_worker.connected
                            else i18n.tr("plc.disconnected")))

    # ================= 语言 =================
    def apply_language(self, lang):
        i18n.set_lang(lang)
        self.cfg["language"] = lang
        save_config(self.cfg)
        self._rebuild_ui()

    def _rebuild_ui(self):
        for dlg in list(self._dialogs.values()):
            dlg.close()
            dlg.deleteLater()
        self._dialogs.clear()
        self.setCentralWidget(None)
        self.dock_left.deleteLater()
        self.dock_ai.deleteLater()
        self.dock_events.deleteLater()
        self._build_ui()

    def _place_metrics(self):
        """能耗生产图: 仿真模式 -> 左侧物料面板下方(2/3);
        PLC模式 -> 底部活动报警汇总左侧, 与报警汇总等大"""
        self.metrics.setParent(None)
        if self.st.mode == "sim":
            self.sim_left_layout.addWidget(self.metrics, 2)
            self._metrics_in_sim = True
        else:
            # 插入到事件日志(index 0)与报警汇总之间, stretch 2 与报警汇总相同
            self.bottom_layout.insertWidget(1, self.metrics, 2)
            self._metrics_in_sim = False
        self.metrics.show()

    # ================= 模式 =================
    def _update_controls(self):
        """PLC 未连接时: 运行/紧急停车/重置 禁用变暗; ESD 锁定时禁用 ESD 按钮"""
        plc_locked = (self.st.mode == "plc" and not self.st.plc_connected)
        for b in ("btn_run", "btn_reset"):
            btn = getattr(self, b, None)
            if btn is not None:
                btn.setEnabled(not plc_locked)
        esd_btn = getattr(self, "btn_esd", None)
        if esd_btn is not None:
            esd_btn.setEnabled(not plc_locked and not self.st.esd_locked)

    def set_mode(self, mode):
        if mode == self.st.mode:
            return
        self.st.mode = mode
        # 切换模式: 回到默认静止状态, 连接/运行后才有动态
        self.st.running = False
        self.engine.reset()
        if hasattr(self, "btn_run"):
            self.btn_run.setChecked(False)
        if mode == "plc":
            self.left_stack.setCurrentIndex(1)   # 显示 PLC 配置面板, 由用户手动连接
        else:
            self.left_stack.setCurrentIndex(0)
            self._plc_disconnect()
        self.metrics.reset()
        self._place_metrics()
        self._update_controls()
        self._update_statusbar()
        self.st.log_event("status.mode")

    # ================= PLC =================
    def _plc_connect(self):
        # 用 isRunning() 而非直接判断引用: 线程已结束(连接失败/异常退出)时允许重连
        if self.plc_worker and self.plc_worker.isRunning():
            return
        # 残留的已结束 worker 对象清理掉
        if self.plc_worker is not None:
            self.plc_worker.deleteLater()
            self.plc_worker = None
            self.st.plc_connected = False
        self.plc_panel.apply_to_cfg()
        save_config(self.cfg)
        self.plc_worker = PLCWorker(self.cfg)
        self.plc_worker.state_ready.connect(self._on_plc_states)
        self.plc_worker.status.connect(self._on_plc_status)
        self.plc_worker.diag.connect(self._on_plc_diag)
        # 线程结束时(无论成功失败)清理引用, 保证下次可点击连接
        self.plc_worker.finished.connect(self._on_plc_finished)
        self.plc_worker.start()

    def _plc_disconnect(self):
        if not self.plc_worker:
            return
        self.plc_worker.stop_worker()
        self.plc_worker.wait(2000)
        # finished 信号会随后触发 _on_plc_finished 做最终清理, 这里先做状态切换
        self.st.plc_connected = False
        self.plc_panel.set_connected(False)
        self._update_statusbar()
        self._update_controls()

    def _on_plc_finished(self):
        """PLCWorker 线程结束(连接失败/读取错误break/主动stop)后清理引用, 允许再次点击连接"""
        worker = self.plc_worker
        if worker is not None:
            worker.deleteLater()
        self.plc_worker = None
        self.st.plc_connected = False
        self.plc_panel.set_connected(False)
        self._update_statusbar()
        self._update_controls()

    def _on_plc_states(self, states):
        if self.st.mode != "plc":
            return
        d = self.st.devices
        esd_item = states.get("ESD")
        for dev_id, item in states.items():
            if dev_id == "ESD":
                continue
            dev = d.get(dev_id)
            if not dev:
                continue
            dev.temp = item.get("temp", dev.temp)
            dev.press = item.get("press", dev.press)
            if "level" in item:
                dev.level = item["level"]
            if "opening" in item:
                dev.opening = item["opening"]
            if "speed" in item:
                dev.speed = item["speed"]
            if "running" in item:
                dev.running = bool(int(round(item["running"])))
            if "power" in item:
                dev.power = item["power"]
            if "sp_temp" in item:
                dev.sp_temp = item["sp_temp"]
            if "sp_level" in item:
                dev.sp_level = item["sp_level"]
        # ESD 联锁位处理
        if esd_item and "trigger" in esd_item:
            val = int(round(esd_item["trigger"]))
            self.st.esd_trigger_val = val
            if val == 1 and not self.st.esd_locked:
                self._trigger_esd("PLC硬联锁触发")
            elif val == 2 and not self.st.esd_locked:
                self._trigger_esd("人工触发")
            elif val == 0 and self.st.esd_locked \
                    and self.st.esd_reason == "PLC硬联锁触发" \
                    and not self.st.esd_plc_cleared:
                # PLC 侧联锁条件已解除 -> 提示人工确认, 保持锁定直到点"ESD 复位"
                self.st.esd_plc_cleared = True
                self.st.log_event("esd.plc_cleared")
                self.esd_banner.setText(
                    "⚠ PLC 联锁已复位，请确认工艺后点“ESD 复位”按钮")
        # 压力联锁 (PLC 模式): >140 kPa 锁定, <132 自动复位
        press = d["T101"].press
        if press > 140.0 and not self.st.esd_locked:
            self._trigger_esd("超压联锁")
        elif press < 132.0 and self.st.esd_locked and self.st.esd_reason == "超压联锁":
            self._release_esd("压力恢复自动复位")
        # ESD 锁定期间: 阀/泵/加热强制保持归零, 不接受 PLC 回读的设定值
        if self.st.esd_locked:
            self._force_devices_off()
        self.st.flows = compute_flows(d)
        interval = max(0.2, self.cfg["plc"].get("interval", 500) / 1000.0)
        self.st.sim_time += interval
        self._plc_acc += interval
        if self._plc_acc >= 1.0:
            self._plc_acc = 0.0
            self._sample()
        self.plc_panel.update_values(states)
        # PLC 模式: 用真实测点跑分层仲裁 (测点未配置的回路在管理器内部自动跳过)
        if self.st.plc_connected:
            self._run_loops(interval)

    def _on_plc_status(self, text):
        if text in ("connected", "reconnected"):
            was_down = not self.st.plc_connected
            self.st.plc_connected = True
            self.plc_panel.set_connected(True)
            # 仅初次连接/断线恢复时写事件日志; 重连成功给出明确恢复提示
            if text == "reconnected":
                self.plc_panel.set_status(i18n.tr("plc.reconnected"))
                if was_down:
                    self.st.log_event("plc.reconnected")
            else:
                self.st.log_event("plc.connected")
        elif text in ("closed", "reconnecting"):
            was_up = self.st.plc_connected
            self.st.plc_connected = False
            self.plc_panel.set_connected(False)
            if text == "reconnecting":
                # 链路中断, worker 仍存活并在后台自动重连: 画面冻结、状态灯转橙
                self.plc_panel.set_status(i18n.tr("plc.reconnecting"))
                if was_up:
                    self.st.log_event("plc.reconnecting")
            # "closed": worker 退出, 由 _on_plc_finished 做引用清理
        else:
            self.st.plc_connected = False
            # 统一切换为未连接状态, 保证 btn_conn 可重新点击 (按钮状态由 set_connected 控制)
            # set_connected 会先显示"未连接", 下方 set_status 再用诊断文本覆盖
            self.plc_panel.set_connected(False)
            # 错误诊断文本: 面板显示 + 事件日志留痕 (tr 对未知 key 原样返回)
            self.plc_panel.set_status(text)
            self.st.events.append({"t": time.strftime("%H:%M:%S"),
                                   "dev": "", "key": text, "params": {}})
        self._update_controls()
        self._update_statusbar()

    def _on_plc_diag(self, text):
        """软诊断 (单点 DB/偏移配置错误、重连进度): 只显示, 不改变连接状态,
        不冻结画面/动画 —— 连接还活着时个别点错误不应拖垮整个 PLC 状态"""
        self.plc_panel.set_status(text)
        self.st.events.append({"t": time.strftime("%H:%M:%S"),
                               "dev": "", "key": text, "params": {}})
        self._update_statusbar()

    # ================= 设备操作 =================
    def apply_action(self, action, source="manual"):
        dev_id = action.get("device", "")
        param = action.get("param", "")
        value = action.get("value", 0)
        dev = self.st.devices.get(dev_id)
        if dev is None:
            return
        # 操作前 MV 快照 (必须在任何写入之前抓, 供案例库记录"当前值")
        before_value = self.case_store._current_value(self.st, action)
        # ESD 锁定: 禁止所有写操作 (含 AI 建议和手动)
        if self.st.esd_locked:
            self.st.log_event("esd.blocked", dev=dev_id, param=param, v=value)
            return {"ok": False, "review": "blocked_esd",
                    "msg": i18n.tr("ai.r.esd_blocked")}
        if param == "level":
            self.st.log_event("ai.r.action", dev=dev_id, param=param, v=value)
            return {"ok": True, "review": "adopted"}

        # 回路仲裁: 该执行器属于某自动回路时
        lid = self.loop_mgr.loop_of_mv(dev_id, param)
        rec_action = dict(action)
        if lid:
            rec_action["lid"] = lid
            if source == "ai" and self.loop_mgr.loops[lid]["auto"]:
                # AI 建议经人工执行 = 人工接管: 回路无扰转手动, PID 不再抢阀
                self.loop_mgr.set_auto(lid, False)
                self.st.log_event("pid.takeover", dev=dev_id,
                                  loop=i18n.tr(self.loop_mgr.loops[lid]["name"]))
            # source == "manual" 时保持自动, PID 下一拍读到新阀位自动跟踪(无扰)

        # AI 建议安全校验 (手动操作不拦), 顺序:
        #   ① 可测性: 归属回路但 PV/SP 读不到 -> 拦截 (无法校验方向, fail-closed)
        #   ② 死区:   |SP-PV| ≤ big 时无需调节, AI 动作 -> 拦截
        #   ③ 空动作: 建议值=当前值 (无任何调节作用) -> 拦截
        #   ④ 方向:   方向错 -> 镜相翻转后下发 (仅可归属回路的动作)
        #   ⑤ 幅度:   所有 AI 数值动作 (含 FV102 等无回路归属者),
        #             单步变化≤量程10%(0-100→≤10), 超限拦截不下发
        review = "adopted"
        orig_val = None
        if source == "ai" and param in ("opening", "speed", "power"):
            cur_val = before_value
            try:
                av = float(value)
            except (TypeError, ValueError):
                av = None
            orig_val = av

            def _reject(reason, review_tag):
                """统一拦截出口: 事件+案例+返回结构"""
                self.st.log_event("ai.reject", dev=dev_id, reason=reason)
                self.case_store.record_rejected(
                    self.st, rec_action, source="ai",
                    loop_mgr=self.loop_mgr, reason=reason, review=review_tag)
                return {"ok": False, "review": review_tag,
                        "msg": i18n.tr("ai.reject", dev=dev_id, reason=reason)}

            expected = "—"
            # ---- ①②③ 可测性/死区/空动作 (仅可归属回路的动作) ----
            if lid and cur_val is not None and av is not None:
                row_l = self.loop_mgr.loops[lid]
                pv_l = self.loop_mgr._pv(self.st, row_l)
                sp_l = self.loop_mgr._setpoint(self.st, row_l)
                expected = self.case_store._expected_direction(
                    self.loop_mgr, self.st, rec_action)
                if pv_l is None or sp_l is None:
                    return _reject("测点缺失, 无法校验调节方向",
                                   "rejected_nosignal")
                if expected == "hold":
                    dev_l = abs(float(sp_l) - float(pv_l))
                    unit = "%" if row_l["pv_field"] == "level" else "°C" \
                        if row_l["pv_field"] == "temp" else ""
                    return _reject(f"偏差{dev_l:.1f}{unit}在死区"
                                   f"(±{row_l['big']:g}{unit})内, 无需调节",
                                   "rejected_deadband")
                if abs(av - cur_val) <= 0.01:
                    return _reject("建议值与当前值相同, 无调节作用",
                                   "rejected_noop")
            # 调试: 记录方向校验的关键量
            try:
                from .config import LOG_DIR
                import os as _os
                _os.makedirs(LOG_DIR, exist_ok=True)
                with open(_os.path.join(LOG_DIR, "ai_direction_debug.log"),
                          "a", encoding="utf-8") as _f:
                    _f.write(f"[{time.strftime('%H:%M:%S')}] "
                             f"dev={dev_id} lid={lid} "
                             f"expected={expected if lid else '—(无回路)'} "
                             f"current={cur_val} value={av} param={param}\n")
            except Exception:
                pass
            # ---- ④ 方向翻转: 偏差超死区且方向错误 ----
            if lid and expected not in ("hold", "—") \
                    and cur_val is not None and av is not None:
                if av > cur_val + 0.01:
                    actual_dir = "increase"
                elif av < cur_val - 0.01:
                    actual_dir = "decrease"
                else:
                    actual_dir = "hold"
                if actual_dir != expected:
                    # 翻转: 以当前值为镜相反转 (50→45 变成 50→55), 再 clamp 0-100
                    flipped = max(0.0, min(100.0, 2.0 * cur_val - av))
                    self.st.log_event("ai.flip", dev=dev_id,
                                      reason=f"方向翻转 {actual_dir}→{expected}")
                    try:
                        from .config import LOG_DIR
                        import os as _os
                        _os.makedirs(LOG_DIR, exist_ok=True)
                        with open(_os.path.join(LOG_DIR, "ai_direction_debug.log"),
                                  "a", encoding="utf-8") as _f:
                            _f.write(f"[{time.strftime('%H:%M:%S')}] FLIP "
                                     f"dev={dev_id} {av}→{flipped:.1f} "
                                     f"cur={cur_val} expected={expected}\n")
                    except Exception:
                        pass
                    av = flipped
                    value = flipped
                    action["value"] = flipped       # 后续下发用翻转值
                    rec_action["value"] = flipped   # 案例记录的"实际下发值"同步
                    review = "flipped"
            # ---- ⑤ 幅度校验 (所有 AI 数值动作, 含无回路归属者) ----
            if cur_val is not None and av is not None \
                    and abs(av - cur_val) > 10.0 + 0.01:
                return _reject("幅度过大, 单次调整不得超过10%",
                               "rejected_magnitude")

        if self.st.mode == "plc" and self.plc_worker and self.plc_worker.connected:
            self.plc_worker.write_param(dev_id, param, value)
        # 本地即时生效 (模拟模式 / PLC回写前的乐观更新)
        if param == "opening":
            dev.opening = float(max(0, min(100, value)))
        elif param == "speed":
            dev.speed = float(max(0, min(100, value)))
        elif param == "power":
            dev.power = float(max(0, min(100, value)))
        elif param == "running":
            dev.running = bool(value)
        elif param in ("sp_temp", "sp_level"):
            setattr(dev, param, float(value))
        if param != "level":
            param_label = {"opening": i18n.tr("field.opening"),
                           "speed": i18n.tr("field.speed"),
                           "power": i18n.tr("field.power"),
                           "running": i18n.tr("field.running"),
                           "sp_temp": i18n.tr("field.sp_temp"),
                           "sp_level": i18n.tr("field.sp_level")}.get(param, param)
            self.st.log_event("ai.r.action", dev=dev_id, param=param_label,
                              v=float(value))
        # 学习案例: 记录本次操作及人工审核处置, 60 仿真秒后评估效果
        # review 仅 AI 审核流程有值; manual/pid 不是审核对象, 留空
        self.case_store.record_action(self.st, rec_action, source=source,
                                      loop_mgr=self.loop_mgr,
                                      review=(review if source == "ai" else ""),
                                      original_value=orig_val,
                                      before_value=before_value)
        return {"ok": True, "review": review, "original": orig_val,
                "final": (float(value) if isinstance(value, (int, float))
                          else value)}

    def open_device_dialog(self, dev_id):
        dlg = self._dialogs.get(dev_id)
        if dlg and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        # 从点表提取该设备的设定值点: {字段: 是否可写}
        sp_fields = {}
        if self.st.mode == "plc":
            for t in get_tags(self.cfg):
                if t.get("dev") == dev_id and t.get("field") in (
                        "sp_temp", "sp_level"):
                    sp_fields[t["field"]] = "W" in str(t.get("rw", "R")).upper()
        dlg = DeviceDialog(self.st, dev_id, self.advisor, self.apply_action,
                           loop_mgr=self.loop_mgr, sp_fields=sp_fields,
                           parent=self)
        dlg.finished.connect(lambda _=None, k=dev_id: self._dialogs.pop(k, None))
        self._dialogs[dev_id] = dlg
        dlg.show()

    # ================= PID 下发 =================
    def _apply_pid_write(self, item):
        """PID 输出直接下发 (限幅内免确认): 仿真本地生效 / PLC 模式写寄存器"""
        dev = self.st.devices.get(item["dev"])
        if dev is None:
            return
        value = float(item["value"])
        if item["param"] == "opening":
            dev.opening = value
        elif item["param"] == "speed":
            dev.speed = value
        elif item["param"] == "power":
            dev.power = value
        if self.st.mode == "plc" and self.plc_worker and self.plc_worker.connected:
            self.plc_worker.write_param(item["dev"], item["param"], value)

    def _run_loops(self, dt):
        """执行一拍分层仲裁: PID 微调直接下发; 大偏差升级 AI; 案例记录/评估"""
        st = self.st
        writes, escalations, pid_moves = self.loop_mgr.update(st, dt, st.sim_time)
        for item in writes:
            self._apply_pid_write(item)
        if writes:
            # MV 已变, 立即重算管路流量供粒子动画
            st.flows = compute_flows(st.devices)
        if escalations:
            for lid in escalations:
                self.st.log_event(
                    "pid.escalate", dev=self.loop_mgr.loops[lid]["mv_dev"],
                    loop=i18n.tr(self.loop_mgr.loops[lid]["name"]))
            # 大偏差: PID 继续兜底, 同时请 LLM 出建议(仍需人工确认)
            self.advisor.request_analysis(token="dock")
        # PID 动作入学习库 (大偏差期间每回路每 60 仿真秒一条, 避免刷屏)
        for item in pid_moves:
            lid = item["lid"]
            if st.sim_time - self._pid_case_acc.get(lid, -1e9) >= 60.0:
                self._pid_case_acc[lid] = st.sim_time
                act = {"device": item["dev"], "param": item["param"],
                       "value": round(item["value"], 1),
                       "reason": "PID auto", "lid": lid}
                self.case_store.record_action(st, act, source="pid",
                                              loop_mgr=self.loop_mgr,
                                              before_value=item.get("before"))
        self.case_store.evaluate_pending(st, self.loop_mgr)

    # ================= 仿真循环 =================
    def _toggle_run(self, on):
        self.st.running = on
        self.btn_run.setText(("⏸ " + i18n.tr("sim.pause")) if on else ("▶ " + i18n.tr("sim.run")))

    def _reset_sim(self):
        self.engine.reset()
        self.loop_mgr.reset()       # PID 状态复位 (手自动标志保留)
        self.metrics.reset()
        self._sample()
        self.st.log_event("sim.reset")

    def _esd(self):
        """紧急停车按钮: 写 ESD_Trigger=2, 由 PLC 硬联锁接管; 上位机同步锁定"""
        st = self.st
        if st.mode == "plc" and self.plc_worker and self.plc_worker.connected:
            self.plc_worker.write_param("ESD", "trigger", 2)
        # 本地状态同步 (PLC 硬联锁会实际关阀/停泵/切加热)
        st.running = False
        self.btn_run.setChecked(False)
        self.loop_mgr.all_manual()
        self._force_devices_off()
        self._trigger_esd("人工触发")

    def _force_devices_off(self):
        """本地设备全部归零: 阀门关闭 / 泵停止 / 加热切断"""
        for dev in self.st.devices.values():
            if dev.dtype == "valve":
                dev.opening = 0.0
            elif dev.dtype == "pump":
                dev.running = False
                dev.speed = 0.0
            elif dev.dtype == "exchanger":
                dev.power = 0.0

    def _trigger_esd(self, reason):
        """ESD 锁定: 禁止所有写操作 + 记录事件"""
        if self.st.esd_locked:
            return
        self.st.esd_locked = True
        self.st.esd_reason = reason
        self.st.esd_plc_cleared = False
        # 自动联锁路径 (PLC ESD_Trigger=1 / 超压) 也立即本地停车
        self.st.running = False
        if hasattr(self, "btn_run"):
            self.btn_run.setChecked(False)
        self.loop_mgr.all_manual()
        self._force_devices_off()
        self.st.log_event("esd.trigger", reason=reason)
        # 记录到 cases.jsonl
        try:
            from .case_store import snapshot as cs_snap
            rec = {
                "t": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "esd",
                "outcome": "triggered",
                "reason": reason,
                "before": cs_snap(self.st),
            }
            import os as _os
            from .config import DATA_DIR
            _os.makedirs(DATA_DIR, exist_ok=True)
            import json as _json
            with open(_os.path.join(DATA_DIR, "cases.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        self._update_esd_ui()

    def _release_esd(self, reason):
        """ESD 解锁"""
        if not self.st.esd_locked:
            return
        self.st.esd_locked = False
        self.st.esd_reason = ""
        self.st.esd_plc_cleared = False
        self.st.log_event("esd.release", reason=reason)
        try:
            from .case_store import snapshot as cs_snap
            rec = {
                "t": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": "esd",
                "outcome": "released",
                "reason": reason,
                "before": cs_snap(self.st),
            }
            import os as _os
            from .config import DATA_DIR
            _os.makedirs(DATA_DIR, exist_ok=True)
            import json as _json
            with open(_os.path.join(DATA_DIR, "cases.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        self._update_esd_ui()

    def _esd_reset(self):
        """ESD 复位按钮: 确认后写 ESD_Trigger=0 并解锁"""
        from PySide6.QtWidgets import QMessageBox
        ret = QMessageBox.question(
            self, "ESD 复位",
            "确认复位 ESD？\n请确认工艺条件已恢复正常。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        st = self.st
        if st.mode == "plc" and self.plc_worker and self.plc_worker.connected:
            self.plc_worker.write_param("ESD", "trigger", 0)
        self._release_esd("人工复位")

    def _update_esd_ui(self):
        """根据 esd_locked 更新横幅/按钮/AI面板状态"""
        locked = self.st.esd_locked
        self.esd_banner.setVisible(locked)
        if locked:
            self.esd_banner.setText(f"⚠ ESD 已触发 — {self.st.esd_reason}")
        self.btn_esd_reset.setVisible(locked)
        self.btn_esd.setEnabled(not locked)   # 锁定时禁用 ESD 按钮, 防止重复触发
        # AI 面板锁定提示
        if hasattr(self, "ai_dock_w") and self.ai_dock_w:
            self.ai_dock_w.set_esd_locked(locked)
        self._update_controls()

    def _on_speed(self, factor):
        self.st.speed = float(factor)

    # ================= 画布缩放 =================
    def eventFilter(self, obj, ev):
        sc = getattr(self, "sc", None)
        if ev.type() == QEvent.Resize and getattr(self, "_auto_fit", False) \
                and sc is not None and obj is sc.viewport():
            self._apply_fit()
        return super().eventFilter(obj, ev)

    def _apply_fit(self):
        vp = self.sc.viewport()
        z = self.canvas.fit_zoom(vp.width(), vp.height())
        # 字号保底: 整图适应比过小时维持最低缩放, 宁可出滚动条也要字清楚
        z = max(z, FIT_FLOOR_Z)
        self.canvas.set_zoom(z)
        self.lb_zoom.setText(f"{z * 100:.0f}%")

    # ================= 窗口几何 / 专注模式 =================
    def _restore_geometry(self):
        """按屏幕智能取初始尺寸(最小1280x720并居中), 或恢复上次窗口/面板布局"""
        ui = self.cfg.get("ui") or {}
        restored = False
        geom = ui.get("geom")
        if isinstance(geom, list) and len(geom) == 4:
            try:
                x, y, w, h = (int(v) for v in geom)
                if w >= 900 and h >= 560:
                    scr = self.screen().availableGeometry()
                    # 标题栏位置至少要在当前屏幕附近可见
                    if scr.adjusted(-120, -120, 120, 120).contains(QRect(x, y, 1, 1)):
                        self.setGeometry(x, y, w, h)
                        restored = True
            except Exception:
                restored = False
        if not restored:
            scr = self.screen().availableGeometry()
            w = max(1280, min(int(scr.width() * 0.92), scr.width()))
            h = max(720, min(int(scr.height() * 0.92), scr.height()))
            self.setGeometry(scr.x() + (scr.width() - w) // 2,
                             scr.y() + (scr.height() - h) // 2, w, h)
        state = ui.get("state")
        if state:
            try:
                self.restoreState(bytes.fromhex(state))
            except Exception:
                pass
        # 纠正异常面板宽度: 保证中央 DCS 画布至少 640px
        try:
            lw, rw = self.dock_left.width(), self.dock_ai.width()
            cap = max(320, self.width() - 640)
            if lw + rw > cap or lw > 460 or rw > 420:
                lw, rw = min(lw, 380), min(rw, 320)
                if lw + rw > cap:
                    s = cap / (lw + rw)
                    lw, rw = int(lw * s), int(rw * s)
                self.resizeDocks([self.dock_left, self.dock_ai],
                                 [lw, rw], Qt.Horizontal)
        except Exception:
            pass
        if ui.get("focus"):
            QTimer.singleShot(120, lambda: self._toggle_focus(True))

    def _toggle_focus(self, on):
        """专注模式: 隐藏左右下停靠面板, 让 DCS 图占满 (F11 / 工具栏按钮)"""
        on = bool(on)
        self._focus = on
        for d in (getattr(self, "dock_left", None),
                  getattr(self, "dock_ai", None),
                  getattr(self, "dock_events", None)):
            if d is not None:
                d.setVisible(not on)
        if hasattr(self, "act_focus"):
            self.act_focus.blockSignals(True)
            self.act_focus.setChecked(on)
            self.act_focus.blockSignals(False)
        if hasattr(self, "btn_focus"):
            self.btn_focus.blockSignals(True)
            self.btn_focus.setChecked(on)
            self.btn_focus.blockSignals(False)
        if getattr(self, "_auto_fit", True):
            QTimer.singleShot(0, self._apply_fit)

    # ================= 控制回路设置 =================
    def _open_loops(self):
        dlg = LoopDialog(self.loop_mgr, self)
        if dlg.exec() == QDialog.Accepted:
            self._sync_loop_switches()

    def _open_experiment(self):
        """自动实验对话框 (毕业设计数据采集)"""
        import traceback, os as _os
        try:
            from .experiment_dialog import ExperimentDialog
            dlg = ExperimentDialog(self, self)
            dlg.exec()
        except Exception:
            # 把 traceback 写到 exe 同目录的 crash_experiment.log
            try:
                log_path = _os.path.join(
                    _os.path.dirname(getattr(_os.sys, "executable", ".")),
                    "crash_experiment.log")
                with open(log_path, "w", encoding="utf-8") as _f:
                    _f.write(traceback.format_exc())
            except Exception:
                pass

    def _sync_loop_switches(self):
        """设置界面关闭后: 处理手/自动切换的无扰初始化"""
        for lid, on in self.loop_mgr.take_pending_switches(self.st):
            row = self.loop_mgr.loops[lid]
            self.st.log_event("pid.auto_on" if on else "pid.auto_off",
                              dev=row["mv_dev"], loop=i18n.tr(row["name"]))
        self.loop_mgr.save_to_cfg()
        save_config(self.cfg)

    # ================= 学习案例导出 =================
    def export_cases(self):
        dst, _ = QFileDialog.getSaveFileName(
            self, i18n.tr("act.export_cases"),
            os.path.join(os.path.expanduser("~"), "Desktop", "cases.csv"),
            "CSV (*.csv)")
        if not dst:
            return
        try:
            self.case_store.export_csv(dst)
            QMessageBox.information(self, i18n.tr("confirm"),
                                    i18n.tr("msg.cases_exported", path=dst))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("confirm"), str(e))

    def _ignore_ai_action(self, action):
        """AI 建议被忽略 -> 记为 rejected 案例 (审核处置=用户忽略)"""
        self.case_store.record_rejected(self.st, action, source="ai",
                                        loop_mgr=self.loop_mgr,
                                        reason="用户忽略", review="ignored")

    def _zoom_fit(self):
        self._auto_fit = self.btn_fit.isChecked()
        if self._auto_fit:
            self._apply_fit()

    def _zoom_manual(self, factor):
        self._auto_fit = False
        self.btn_fit.setChecked(False)
        self.canvas.set_zoom(self.canvas.zoom() * factor)
        self.lb_zoom.setText(f"{self.canvas.zoom() * 100:.0f}%")

    def _zoom_actual(self):
        self._auto_fit = False
        self.btn_fit.setChecked(False)
        self.canvas.set_zoom(1.0)
        self.lb_zoom.setText("100%")

    def _sample(self):
        st = self.st
        t = st.sim_time
        for dev_id, dev in st.devices.items():
            st.push_hist(dev_id, "temp", t, dev.temp)
            st.push_hist(dev_id, "press", t, dev.press)
            if dev.dtype == "tank":
                st.push_hist(dev_id, "level", t, dev.level)
            if dev.dtype == "valve":
                st.push_hist(dev_id, "opening", t, dev.opening)
            if dev.dtype == "pump":
                st.push_hist(dev_id, "speed", t, dev.speed)
            if dev.dtype == "exchanger":
                st.push_hist(dev_id, "power", t, dev.power)
            if dev.dtype == "column":
                st.push_hist(dev_id, "temp", t, dev.temp)

    def _on_loop(self):
        st = self.st
        # 系统活动状态: 仿真模式下运行中 / PLC 模式下已连接; ESD 锁定时一律冻结
        active = not st.esd_locked and \
                 ((st.mode == "sim" and st.running) or
                  (st.mode == "plc" and st.plc_connected))
        # 仿真推进 (仅模拟模式运行中, ESD 锁定时冻结)
        if st.mode == "sim" and st.running and not st.esd_locked:
            dt = 0.2 * st.speed
            self.engine.step(dt)
            self._run_loops(dt)      # 分层仲裁: 小偏差 PID / 大偏差升级 AI
            self._acc += dt
            if self._acc >= 1.0:
                self._acc = 0.0
                self._sample()
        # 粒子动画: 暂停/急停/PLC未连接时冻结, 恢复后接着动
        if active:
            self.canvas.advance_anim()
        self.canvas.update()
        self._update_statusbar()
        self.alarm_panel.update_panel()

        # 数据记录 (每秒)
        self._log_acc += 0.2
        if self._log_acc >= 1.0:
            self._log_acc = 0.0
            row = {}
            for dev_id, dev in st.devices.items():
                row[dev_id + "_T"] = dev.temp
                row[dev_id + "_P"] = dev.press
                if dev.dtype == "tank":
                    row[dev_id + "_L"] = dev.level
                if dev.dtype == "valve":
                    row[dev_id + "_OP"] = dev.opening
                if dev.dtype == "pump":
                    row[dev_id + "_SPD"] = dev.speed
                    row[dev_id + "_RUN"] = 1.0 if dev.running else 0.0
            self.logger.write_row(st.sim_time, row)
            self.trend.update_curves()
            if active:
                self.metrics.update_metrics(dt_s=1.0 * st.speed)

        # 事件列表刷新
        if len(st.events) != self._event_idx:
            if self._event_idx > len(st.events):
                self._render_all_events()
            else:
                while self._event_idx < len(st.events):
                    ev = st.events[self._event_idx]
                    self.event_list.addItem(format_event(ev))
                    self.event_list.scrollToBottom()
                    self._event_idx += 1
                self.logger.write_event(format_event(st.events[-1]))

        # AI 自主运行 (需人工确认)
        self._ai_acc += 0.2
        if st.auto_ai and self._ai_acc >= 15.0:
            self._ai_acc = 0.0
            plc_ok = self.plc_worker and self.plc_worker.connected
            if (st.mode == "sim" and st.running) or (st.mode == "plc" and plc_ok):
                self.advisor.request_analysis(token="dock")

    # ================= 事件/物料 =================
    def _render_all_events(self):
        self.event_list.clear()
        for ev in list(self.st.events)[-60:]:
            self.event_list.addItem(format_event(ev))
        self._event_idx = len(self.st.events)
        self.event_list.scrollToBottom()

    def _on_material(self, name):
        self.st.log_event("mat.title", v=name)

    def _clear_trend(self):
        self.st.clear_hist()
        self.trend.update_curves()

    # ================= 导出/关闭 =================
    def export_log(self):
        dst, _ = QFileDialog.getSaveFileName(
            self, i18n.tr("act.export_log"), os.path.join(os.path.expanduser("~"),
            "Desktop", "distillation_logs.zip"), "ZIP (*.zip)")
        if not dst:
            return
        try:
            self.logger.export_zip(dst)
            QMessageBox.information(self, i18n.tr("confirm"),
                                    i18n.tr("msg.exported", path=dst))
        except Exception as e:
            QMessageBox.warning(self, i18n.tr("confirm"), str(e))

    def closeEvent(self, ev):
        ret = QMessageBox.question(self, i18n.tr("act.exit"), i18n.tr("q.quit"))
        if ret != QMessageBox.Yes:
            ev.ignore()
            return
        # 记忆窗口尺寸/位置/Dock 布局/专注状态
        g = self.geometry()
        self.cfg["ui"] = {
            "geom": [g.x(), g.y(), g.width(), g.height()],
            "state": bytes(self.saveState()).hex(),
            "focus": bool(getattr(self, "_focus", False))}
        self._plc_disconnect()
        save_config(self.cfg)
        ev.accept()
