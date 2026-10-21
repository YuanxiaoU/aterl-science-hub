# -*- coding: utf-8 -*-
"""Aterl-DistSim 精馏装置仿真与控制系统 - 入口"""
import sys

from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

DARK_QSS = """
* { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 12px; outline: none; }
QWidget { background: #0f1620; color: #dbe6f2; }
QMainWindow, QDialog { background: #0f1620; }
QToolTip { background: #1b2838; color: #e6f0fa; border: 1px solid #3b6088;
           border-radius: 4px; padding: 4px 8px; }

/* ===== 菜单栏 / 菜单 ===== */
QMenuBar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #18233a, stop:1 #111a2c); border-bottom: 1px solid #2a4260;
        padding: 2px; }
QMenuBar::item { background: transparent; padding: 6px 14px; border-radius: 4px;
        color: #c7d6e8; }
QMenuBar::item:selected { background: #274b73; color: #ffffff; }
QMenu { background: #16222f; border: 1px solid #33506e; border-radius: 6px;
        padding: 4px; }
QMenu::item { padding: 6px 24px 6px 16px; border-radius: 4px; color: #d5e2f0; }
QMenu::item:selected { background: #2a5180; color: #ffffff; }
QMenu::separator { height: 1px; background: #2a4058; margin: 4px 8px; }

/* ===== 选项卡 ===== */
QTabWidget::pane { border: 1px solid #26394f; border-radius: 6px;
        background: #101925; }
QTabBar::tab { background: #16222f; color: #8fa7c0; padding: 7px 22px;
        margin-right: 3px; border: 1px solid #26394f; border-bottom: none;
        border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #2b5a8c, stop:1 #21446d); color: #ffffff; font-weight: bold;
        border-color: #3f75ac; }
QTabBar::tab:hover:!selected { background: #1d2e42; color: #dbe6f2; }

/* ===== 按钮 ===== */
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #2d5a88, stop:1 #234a72); border: 1px solid #4071a6;
        border-radius: 4px; padding: 5px 14px; color: #eaf3fc; font-weight: 500; }
QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #3770aa, stop:1 #2b5c8c); border-color: #5b93cf; }
QPushButton:pressed { background: #1c3a5c; border-color: #31567f; }
QPushButton:checked { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #2f7d57, stop:1 #246044); border-color: #45a87c; }
QPushButton:disabled { background: #1a2430; border-color: #29343f;
        color: #5a6b7d; }

/* ===== 输入控件 ===== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #141e2c; border: 1px solid #30465e; border-radius: 4px;
    padding: 4px 8px; selection-background-color: #2f679f; color: #e4eef8; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #4f8fc9; background: #16222f; }
QLineEdit:disabled, QSpinBox:disabled { background: #121a24; color: #5a6b7d; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #16222f; border: 1px solid #33506e;
    border-radius: 4px; selection-background-color: #2a5180; outline: none; }

/* ===== 分组框 ===== */
QGroupBox { border: 1px solid #2c4258; border-radius: 7px; margin-top: 12px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(28,42,60,150), stop:1 rgba(18,28,40,120)); padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
    left: 12px; padding: 2px 10px; color: #6fb6ea; font-weight: bold;
    background: #162333; border: 1px solid #2c4258; border-radius: 4px; }

/* ===== 表格 / 列表 ===== */
QTableWidget { background: #0f1823; gridline-color: #22354a; border: 1px solid #26394f;
    border-radius: 4px; alternate-background-color: #13202e; }
QTableWidget::item { padding: 3px 6px; }
QTableWidget::item:selected { background: #2a5180; }
QHeaderView::section { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #1e3145, stop:1 #182738); border: 1px solid #26394f;
    padding: 5px 4px; color: #9fc0dd; font-weight: bold; }
QListWidget { background: #0d1620; border: 1px solid #26394f; border-radius: 5px;
    alternate-background-color: #111c28; }
QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #1a2a3c; }
QListWidget::item:selected { background: #26496f; }
QTextEdit, QPlainTextEdit { background: #0d1620; border: 1px solid #26394f;
    border-radius: 5px; selection-background-color: #2f679f; }

/* ===== 停靠窗口 ===== */
QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
QDockWidget::title { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #1b2a40, stop:1 #14202f); padding: 6px 10px; color: #9fc0dd;
    font-weight: bold; border: 1px solid #2a4260; border-bottom: none; }
QDockWidget { color: #c7d6e8; }

/* ===== 滑块 ===== */
QSlider::groove:horizontal { height: 6px; border-radius: 3px;
    background: #1a2a3c; border: 1px solid #26394f; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #3f8fc9, stop:1 #57b3e8); border-radius: 3px; }
QSlider::handle:horizontal { width: 15px; height: 15px; margin: -5px 0;
    background: qradialgradient(cx:0.5,cy:0.4,radius:0.6,
    stop:0 #bfe3ff, stop:0.6 #4f9fd8, stop:1 #2b6ca3);
    border: 1px solid #8cc4ee; border-radius: 8px; }
QSlider::handle:horizontal:hover { background: qradialgradient(cx:0.5,cy:0.4,radius:0.6,
    stop:0 #ffffff, stop:0.6 #6fb6ea, stop:1 #3178b5); }

/* ===== 滚动条 ===== */
QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c4358; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3d5c79; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2c4358; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #3d5c79; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ===== 状态栏 / 标签 / 复选框 ===== */
QStatusBar { background: #0d1520; border-top: 1px solid #2a4260; color: #9fc0dd; }
QStatusBar QLabel { padding: 0 8px; color: #b9cfe2; }
QLabel { background: transparent; }
QCheckBox { spacing: 6px; color: #d5e2f0; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #3f6388;
    border-radius: 3px; background: #141e2c; }
QCheckBox::indicator:hover { border-color: #5b93cf; }
QCheckBox::indicator:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
    stop:0 #2f7d57, stop:1 #45a87c); border-color: #5fd09a; }
QSplitter::handle { background: #26394f; }
QScrollArea { background: #0a0f16; border: none; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Aterl-DistSim")
    app.setOrganizationName("Aterl")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(DARK_QSS)
    # 鼠标滚轮线性化: ItemView 像素平滑滚动 + 下拉框/数值框未聚焦时不被滚轮误改
    from core.wheel_smooth import WheelSmoother
    app.installEventFilter(WheelSmoother())
    # 应用图标 (内嵌资源, onefile 免外部路径)
    try:
        from ui.logo_asset import logo_png_bytes
        pm = QPixmap()
        pm.loadFromData(logo_png_bytes())
        if not pm.isNull():
            app.setWindowIcon(QIcon(pm))
    except Exception:
        pass
    from ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
