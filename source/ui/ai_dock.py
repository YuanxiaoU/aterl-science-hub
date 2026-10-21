# -*- coding: utf-8 -*-
"""AI 智能助手面板: 本地模型配置 / 待确认建议(自主运行) / 建议历史"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QGroupBox, QLabel, QLineEdit, QPushButton,
                               QCheckBox, QTextEdit, QFrame, QScrollArea,
                               QComboBox)

from core import i18n
from core.config import save_config


class SuggestRow(QFrame):
    """单条待确认建议 (文字完整换行显示, 按钮在右下)"""
    def __init__(self, action, on_apply, on_ignore, parent=None):
        super().__init__(parent)
        self.action = action
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame{background:#1b2836; border:1px solid #35506b; border-radius:4px;}"
                           "QLabel{border:none;} QPushButton{border:none;}")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(6)
        txt = f"[{action['device']}] {action['reason']}"
        if action["param"] != "level":
            txt += f"  →  {action['param']}={action['value']:.0f}%"
        lb = QLabel(txt)
        lb.setWordWrap(True)
        lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lb.setMinimumHeight(34)
        v.addWidget(lb)
        h = QHBoxLayout()
        h.addStretch(1)
        self.b_apply = QPushButton(i18n.tr("ai.apply"))
        self.b_apply.clicked.connect(lambda: on_apply(self))
        self.b_ignore = QPushButton(i18n.tr("ai.ignore"))
        self.b_ignore.clicked.connect(lambda: on_ignore(self))
        h.addWidget(self.b_apply)
        h.addWidget(self.b_ignore)
        v.addLayout(h)

    def set_esd_locked(self, locked):
        self.b_apply.setEnabled(not locked)
        # 已被安全层拦截的行, 忽略按钮始终保持禁用, 解锁也不恢复
        self.b_ignore.setEnabled(not locked and not getattr(self, "_blocked", False))
        if locked:
            self.b_apply.setText("🔒 ESD锁定")
        else:
            self.b_apply.setText(i18n.tr("ai.apply"))

    def mark_rejected(self, msg):
        """安全校验未通过: 保留建议行, 执行/忽略按钮均置灰 (防止拦截后
        再点忽略导致同一条建议重复记录), 红色显示拦截原因"""
        self._blocked = True
        self.b_apply.setEnabled(False)
        self.b_apply.setText("已拦截")
        self.b_ignore.setEnabled(False)
        lb = QLabel(f"<span style='color:#ff6b6b'>✗ {msg}</span>")
        lb.setWordWrap(True)
        self.layout().addWidget(lb)


class AiDock(QWidget):
    def __init__(self, st, advisor, apply_action, on_ignore=None, parent=None):
        super().__init__(parent)
        self.st = st
        self.advisor = advisor
        self.apply_action = apply_action
        self.on_ignore = on_ignore        # 建议被忽略 -> 学习案例记录
        self._build()
        advisor.status_changed.connect(self._on_status)
        advisor.suggestions_ready.connect(self._on_suggestions)
        self._rows = []

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        box = QGroupBox(i18n.tr("ai.dock_title"))
        v = QVBoxLayout(box)

        g = QGridLayout()
        g.addWidget(QLabel(i18n.tr("ai.url")), 0, 0)
        self.ed_url = QLineEdit(self.advisor.cfg["ollama_url"])
        g.addWidget(self.ed_url, 0, 1)
        g.addWidget(QLabel(i18n.tr("ai.model")), 1, 0)
        # 模型选择: 可编辑下拉框 — 下拉列出 Ollama 已拉取的全部模型,
        # 也可手动输入精确标签; 选中即保存并立即生效 (请求时实时读取)
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_model.addItem(self.advisor.cfg["ai_model"])
        self.cb_model.setCurrentText(self.advisor.cfg["ai_model"])
        self.cb_model.setInsertPolicy(QComboBox.NoInsert)
        self.cb_model.setToolTip(
            "下拉选择本地已拉取的模型, 或手动输入 ollama list 中的精确标签\n"
            "(含量化后缀, 必须逐字一致)")
        # 连接默认信号 (int 索引): 新版 PySide6 的 activated 只有 int 重载,
        # 处理函数内统一把索引翻译成模型文本, 版本无关
        self.cb_model.activated.connect(self._on_model_activated)
        g.addWidget(self.cb_model, 1, 1)
        b_test = QPushButton(i18n.tr("ai.test"))
        b_test.clicked.connect(self._test)
        g.addWidget(b_test, 0, 2)
        v.addLayout(g)

        self.lb_status = QLabel()
        self.lb_status.setWordWrap(True)
        v.addWidget(self.lb_status)

        self.cb_auto = QCheckBox(i18n.tr("ai.auto"))
        self.cb_auto.setChecked(self.st.auto_ai)
        self.cb_auto.toggled.connect(lambda on: setattr(self.st, "auto_ai", on))
        v.addWidget(self.cb_auto)

        v.addWidget(QLabel(f"<b>{i18n.tr('ai.pending')}</b>"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setAlignment(Qt.AlignTop)
        self.list_lay.setSpacing(4)
        self.scroll.setWidget(self.list_host)
        self.scroll.setMinimumHeight(150)
        v.addWidget(self.scroll, 1)

        v.addWidget(QLabel(f"<b>{i18n.tr('ai.history')}</b>"))
        self.hist = QTextEdit()
        self.hist.setReadOnly(True)
        self.hist.setMinimumHeight(110)
        v.addWidget(self.hist, 1)
        lay.addWidget(box)
        self._refresh_status_text()

    # ---------- 行为 ----------
    def _test(self):
        self.advisor.cfg["ollama_url"] = self.ed_url.text().strip() or \
            self.advisor.cfg["ollama_url"]
        self.advisor.cfg["ai_model"] = self.cb_model.currentText().strip() or \
            self.advisor.cfg["ai_model"]
        self.lb_status.setText("...")
        self.advisor.check()

    def _on_model_activated(self, idx):
        """下拉选中模型: 立即写入配置并持久化, 下次 AI 请求即生效。
        idx 为activated信号的索引 (新版 PySide6 仅 int 重载), 翻译成模型文本。"""
        if isinstance(idx, int):
            name = self.cb_model.itemText(idx)   # 无效索引返回空串
        else:
            name = str(idx)
        name = name.strip()
        if not name:
            return
        self.advisor.cfg["ai_model"] = name
        save_config(self.advisor.cfg)
        self.lb_status.setText(f"已切换模型: {name} (点「测试」验证连接)")

    def _on_status(self, online, msg):
        self.lb_status.setText(("🟢 " if online else "🟡 ") + msg)
        self._refresh_models()

    def _refresh_models(self):
        """用 advisor.check() 探测到的模型列表刷新下拉选项 (保留当前选择)"""
        models = [m for m in getattr(self.advisor, "models", []) if m]
        if not models:
            return
        cur = self.cb_model.currentText().strip()
        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        self.cb_model.addItems(models)
        if cur and cur not in models:
            self.cb_model.addItem(cur)
        self.cb_model.setCurrentText(cur)
        self.cb_model.blockSignals(False)

    def _refresh_status_text(self):
        pass

    def _on_suggestions(self, actions, text, token):
        if token is not None and not (isinstance(token, str) and token == "dock"):
            return
        if not actions:
            self._clear_rows()
            self.hist.append("· " + text)
            return
        self._clear_rows()
        for a in actions:
            row = SuggestRow(a, self._apply_row, self._ignore_row)
            row.set_esd_locked(self.st.esd_locked)
            self.list_lay.addWidget(row)
            self._rows.append(row)
        self.hist.append(f"<br><b>--- {text}</b>")

    def _clear_rows(self):
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows = []

    def set_esd_locked(self, locked):
        """ESD 锁定时禁用所有建议的执行按钮"""
        for r in self._rows:
            r.set_esd_locked(locked)

    def _apply_row(self, row):
        # apply_action 返回人工审核处置: adopted/flipped/rejected_magnitude/blocked_esd
        res = self.apply_action(row.action, "ai") or {}
        if not res.get("ok", False):
            # 拦截/ESD锁定: 建议行保留并标红, 不从列表移除
            msg = res.get("msg", "安全校验未通过")
            row.mark_rejected(msg)
            self.hist.append("· " + msg)
            return
        if res.get("review") == "flipped":
            txt = i18n.tr("ai.r.flipped", dev=row.action["device"],
                          param=row.action["param"],
                          orig=float(res.get("original", 0) or 0),
                          final=float(res.get("final", 0) or 0))
        else:
            txt = i18n.tr("ai.r.action", dev=row.action["device"],
                          param=row.action["param"],
                          v=float(row.action["value"]))
        self.hist.append("· " + txt)
        self.list_lay.removeWidget(row)
        row.deleteLater()
        if row in self._rows:
            self._rows.remove(row)

    def _ignore_row(self, row):
        if self.on_ignore is not None:
            self.on_ignore(row.action)
        self.list_lay.removeWidget(row)
        row.deleteLater()
        if row in self._rows:
            self._rows.remove(row)

    def retranslate(self):
        self.cb_auto.setText(i18n.tr("ai.auto"))
