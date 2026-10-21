# -*- coding: utf-8 -*-
"""自动实验对话框: 选择实验类型/次数/工况数, 启动/暂停/停止/导出, 显示进度"""
import os
import shutil
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QSpinBox, QCheckBox,
    QLabel, QPushButton, QProgressBar, QGroupBox, QFileDialog, QMessageBox,
    QButtonGroup)

from core.experiment import ExperimentRunner, load_cases, EXP_DIR


class _Bridge(QObject):
    """把运行线程的回调转为 Qt 信号 (跨线程安全)"""
    progress = Signal(int, int, int, int, str)   # ci, total, rep, reps, msg
    step = Signal(str)
    done = Signal(str)


class ExperimentDialog(QDialog):
    def __init__(self, main, parent=None):
        super().__init__(parent or main)
        self.main = main
        self.st = main.st
        self.runner = None
        self.setWindowTitle("🧪 自动实验 v2 (毕业设计数据采集)")
        self.resize(560, 460)
        v = QVBoxLayout(self)

        # ---- 实验类型 ----
        gb = QGroupBox("实验类型")
        gv = QVBoxLayout(gb)
        self.rb_a = QRadioButton(
            "类型 A — Prompt 对比: 原始 Prompt vs 强化 Prompt (每工况×2次调用)")
        self.rb_b = QRadioButton(
            "类型 B — 三组对比: B1单回路 / B2多回路无协调 / B3多回路有协调 (×3次调用)")
        self.rb_c = QRadioButton(
            "类型 C — 完整数据采集: 生产配置, 强化 Prompt 全回路 (每工况×1次调用)")
        self.rb_c.setChecked(True)
        # 互斥组 + 点击调试
        grp = QButtonGroup(self)
        grp.addButton(self.rb_a)
        grp.addButton(self.rb_b)
        grp.addButton(self.rb_c)
        for rb, lid in ((self.rb_a, "A"), (self.rb_b, "B"), (self.rb_c, "C")):
            rb.toggled.connect(
                lambda checked, _lid=lid: self._dbg_type(_lid, checked))
        # 深色主题可见样式
        for rb in (self.rb_a, self.rb_b, self.rb_c):
            rb.setStyleSheet(
                "QRadioButton{padding:4px 10px; color:#d9efff;}"
                "QRadioButton::indicator{width:18px;height:18px;}"
                "QRadioButton::indicator:unchecked{"
                "  border:2px solid #6080a0; border-radius:10px; background:#1a2a3a;}"
                "QRadioButton::indicator:checked{"
                "  border:2px solid #40c0ff; border-radius:10px; background:#2060a0;}"
            )
        gv.addWidget(self.rb_a)
        gv.addWidget(self.rb_b)
        gv.addWidget(self.rb_c)
        v.addWidget(gb)

        # ---- 参数 ----
        gp = QGroupBox("参数")
        ph = QHBoxLayout(gp)
        ph.addWidget(QLabel("每工况重复:"))
        self.sp_reps = QSpinBox()
        self.sp_reps.setRange(1, 10)
        self.sp_reps.setValue(3)
        ph.addWidget(self.sp_reps)
        ph.addWidget(QLabel("前 N 个工况 (0=全部30):"))
        self.sp_limit = QSpinBox()
        self.sp_limit.setRange(0, 30)
        self.sp_limit.setValue(0)
        ph.addWidget(self.sp_limit)
        self.cb_exec = QCheckBox("执行AI建议(写回PLC)")
        self.cb_exec.setToolTip("默认观察模式: 只评估校验, 不写回 PLC")
        ph.addWidget(self.cb_exec)
        self.cb_compare = QCheckBox("学习对比(空库+种子库各跑一遍)")
        self.cb_compare.setToolTip("同一批工况跑两遍: 第一遍空库(baseline), "
                                   "第二遍注入种子案例(seed), 输出对照报告 compare_*.md")
        ph.addWidget(self.cb_compare)
        v.addWidget(gp)

        # ---- 模式提示 ----
        self.lb_mode = QLabel()
        v.addWidget(self.lb_mode)

        # ---- 进度 ----
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        v.addWidget(self.bar)
        self.lb_progress = QLabel("等待开始")
        self.lb_progress.setStyleSheet("font-weight:bold;")
        v.addWidget(self.lb_progress)
        self.lb_step = QLabel("")
        v.addWidget(self.lb_step)

        # ---- 按钮 ----
        hb = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始实验")
        self.btn_start.clicked.connect(self._start)
        self.btn_pause = QPushButton("⏸ 暂停")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_export = QPushButton("导出中途数据")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        hb.addWidget(self.btn_start)
        hb.addWidget(self.btn_pause)
        hb.addWidget(self.btn_stop)
        hb.addWidget(self.btn_export)
        hb.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self._close)
        hb.addWidget(btn_close)
        v.addLayout(hb)

        self._bridge = _Bridge()
        self._bridge.progress.connect(self._on_progress)
        self._bridge.step.connect(self.lb_step.setText)
        self._bridge.done.connect(self._on_done)
        self._refresh_mode()

    # ---------- 模式 ----------
    def _dbg_type(self, lid, checked):
        """调试: 每次类型切换写日志, 确认事件是否收到"""
        try:
            import time
            log_path = os.path.join(
                os.path.dirname(getattr(os.sys, "executable", ".")),
                "dialog_debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] type={lid} checked={checked}\n")
        except Exception:
            pass

    def _refresh_mode(self):
        if self.st.mode == "plc":
            conn = bool(self.main.plc_worker and self.main.plc_worker.connected)
            self.lb_mode.setText(
                f"当前模式: PLC ({self.main.cfg['plc']['host']}) — 连接: "
                + ("正常, 将真实写入 DB1.0/8/32 注入工况" if conn
                   else "未连接! 请先在左侧面板连接 PLC"))
        else:
            self.lb_mode.setText("当前模式: 仿真 — 将直接设定设备值注入工况 (无 PLC)")

    # ---------- 运行控制 ----------
    def _cases(self):
        cases = load_cases()
        limit = self.sp_limit.value()
        if self.rb_b.isChecked():
            # 类型 B 在工况 1-13 (单/双/三回路+耦合) 上对比更有意义, 支持限选
            pass
        return cases[:limit] if limit > 0 else cases

    def _start(self):
        cases = self._cases()
        if not cases:
            QMessageBox.warning(self, "自动实验", "找不到 data/test_cases.json")
            return
        if self.st.mode == "plc" and not (
                self.main.plc_worker and self.main.plc_worker.connected):
            QMessageBox.warning(self, "自动实验", "PLC 未连接, 无法注入工况")
            return
        if self.rb_a.isChecked():
            exp_type = "A"
        elif self.rb_b.isChecked():
            exp_type = "B"
        else:
            exp_type = "C"
        # 实验期间关闭界面自动 AI, 避免双重调用; 运行器复位 ESD 走窗口接口
        self._auto_ai_backup = self.st.auto_ai
        self.st.auto_ai = False
        self.runner = ExperimentRunner(
            self.main.cfg, self.st, cases, exp_type=exp_type,
            reps=self.sp_reps.value(), exec_suggestions=self.cb_exec.isChecked(),
            own_poll=False, esd_reset_hook=self._esd_reset_via_window,
            case_store=None, compare=self.cb_compare.isChecked(),
            on_progress=self._bridge.progress.emit,
            on_step=self._bridge.step.emit,
            on_done=self._bridge.done.emit)
        # 实验线程独占 PLC 连接: 暂停主程序轮询, 避免双连接并发被 PLCSIM 踢掉
        self._pause_main_poll(True)
        if self.st.mode == "plc":
            # 等主轮询当前拍结束 (interval 500ms), 确保实验连接建立时无并发
            time.sleep(0.7)
        self._set_running(True)
        self.runner.start()

    def _esd_reset_via_window(self):
        """实验中 ESD 触发: 走窗口的正规复位 (写 0 + 事件 + cases 记录 + UI)"""
        try:
            if self.main.st.esd_locked:
                self.main._release_esd("实验自动复位")
        except Exception:
            pass

    def _pause_main_poll(self, paused):
        """暂停/恢复主程序 PLC 轮询线程 (实验线程独占连接);
        无条件设置标志 — 即使主轮询正在重连, 重连成功后也会立即挂起"""
        try:
            w = self.main.plc_worker
            if w is not None:
                w.set_paused(paused)
        except Exception:
            pass

    def _pause(self):
        if not self.runner:
            return
        paused = not self.runner._paused
        self.runner.pause(paused)
        self.btn_pause.setText("⏵ 继续" if paused else "⏸ 暂停")

    def _stop(self):
        if self.runner:
            self.runner.stop()
            self.lb_step.setText("正在停止...")

    def _export(self):
        if not os.path.exists(EXP_DIR):
            return
        src = getattr(self.runner, "log_file", None) if self.runner else None
        src = src or os.path.join(EXP_DIR, "experiment_log.csv")
        if not os.path.exists(src):
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "导出中途数据", os.path.join(
                EXP_DIR, f"experiment_log_{time.strftime('%H%M%S')}.csv"),
            "CSV (*.csv)")
        if dst:
            shutil.copyfile(src, dst)
            self.lb_step.setText(f"已导出: {dst}")

    def _set_running(self, on):
        for w in (self.rb_a, self.rb_b, self.rb_c, self.sp_reps,
                  self.sp_limit, self.cb_exec, self.cb_compare, self.btn_start):
            w.setEnabled(not on)
        self.btn_pause.setEnabled(on)
        self.btn_stop.setEnabled(on)
        self.btn_export.setEnabled(on)

    # ---------- 回调 ----------
    def _on_progress(self, ci, total, rep, reps, msg):
        self.bar.setMaximum(total * reps)
        self.bar.setValue((ci - 1) * reps + rep)
        self.lb_progress.setText(f"正在测试 {ci}/{total} 工况 (第{rep}/{reps}次): {msg}")

    def _on_done(self, summary_path):
        self._set_running(False)
        self.btn_pause.setText("⏸ 暂停")
        self.st.auto_ai = getattr(self, "_auto_ai_backup", False)
        # 实验结束: 恢复主程序 PLC 轮询 (实验线程已断开自己的连接)
        self._pause_main_poll(False)
        if summary_path:
            self.lb_progress.setText("实验完成")
            self.lb_step.setText(f"报告已生成: {summary_path}")
        else:
            self.lb_step.setText("已停止 (数据已保存, 报告未生成)")

    def _close(self):
        if self.runner and self.runner.is_alive():
            r = QMessageBox.question(
                self, "自动实验", "实验正在运行, 确定停止并关闭?",
                QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
            self.runner.stop()
            self.runner.join(3000)
            self.st.auto_ai = getattr(self, "_auto_ai_backup", False)
        # 确保主轮询恢复 (正常结束时 _on_done 已恢复, 此处兜底)
        self._pause_main_poll(False)
        self.reject()
