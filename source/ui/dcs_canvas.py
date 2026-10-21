# -*- coding: utf-8 -*-
"""DCS 流程图画布: 固定布局, 设备互不遮挡; 点击设备弹出调节窗口"""
import math
import time

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
                           QFontMetrics, QLinearGradient, QRadialGradient,
                           QPainterPath)
from PySide6.QtWidgets import QWidget

from core import i18n

W, H = 1560, 880

# ---------------- 布局定义 (所有矩形互不重叠) ----------------
RECTS = {   # id -> (x, y, w, h)
    "V101": (40, 210, 160, 180),
    "P101": (260, 270, 90, 90),
    "E101": (410, 250, 110, 130),
    "T101": (590, 130, 150, 500),
    "E103": (820, 55, 140, 90),
    "V102": (1020, 80, 150, 130),
    "P102": (1240, 100, 90, 90),
    "V103": (1420, 60, 120, 130),
    "E102": (560, 690, 200, 140),
    "V104": (1020, 690, 150, 140),
}
VALVE_CENTERS = {   # id -> (cx, cy)
    "FV101": (380, 315),
    "FV102": (505, 760),
    "FV103": (785, 130),
    "FV104": (1050, 300),
    "FV105": (1390, 128),
    "FV106": (860, 770),
}
VS = 18   # 阀门半宽

PIPES = [  # (流股key, 折线)
    ("feed", [(200, 315), (590, 315)]),
    ("vapor", [(665, 130), (665, 90), (820, 90)]),
    ("condensate", [(960, 100), (1020, 100)]),
    ("cooling", [(750, 130), (820, 130)]),
    ("cooling", [(960, 130), (1005, 130)]),
    ("reflux", [(1170, 145), (1240, 145)]),
    ("reflux", [(1330, 145), (1390, 145), (1390, 300), (740, 300)]),
    ("distillate", [(1390, 145), (1390, 110), (1420, 110)]),
    ("feed", [(615, 630), (615, 690)]),
    ("vapor", [(665, 690), (665, 630)]),
    ("steam", [(430, 760), (560, 760)]),
    ("bottoms", [(760, 770), (1020, 770)]),
    ("distillate", [(1480, 190), (1480, 240)]),
    ("bottoms", [(1095, 830), (1095, 862)]),
    ("feed", [(10, 315), (40, 315)]),
]
FLOW_PATHS = {  # flow_key -> 折线列表
    "feed": [[(200, 315), (590, 315)], [(615, 630), (615, 690)], [(10, 315), (40, 315)]],
    "vapor": [[(665, 130), (665, 90), (820, 90)], [(665, 690), (665, 630)]],
    "condensate": [[(960, 100), (1020, 100)]],
    "cooling": [[(750, 130), (820, 130)], [(960, 130), (1005, 130)]],
    "reflux": [[(1170, 145), (1240, 145)], [(1330, 145), (1390, 145), (1390, 300), (740, 300)]],
    "distillate": [[(1390, 145), (1390, 110), (1420, 110)], [(1480, 190), (1480, 240)]],
    "steam": [[(430, 760), (560, 760)]],
    "bottoms": [[(760, 770), (1020, 770)], [(1095, 830), (1095, 862)]],
}
STREAM_COLOR = {
    "feed": "#43c46f", "vapor": "#e0956a", "steam": "#e05a5a",
    "cooling": "#4f9fd8", "condensate": "#d8a44f", "reflux": "#b48fd8",
    "distillate": "#d8b24f", "bottoms": "#c88fd0",
}
LEGEND = ["feed", "vapor", "steam", "cooling", "reflux", "distillate", "bottoms"]

COL_BG = QColor("#101823")
COL_PIPE_CASE = QColor("#1c3349")
COL_PIPE = QColor("#4a76a0")
COL_DEV = QColor("#1d2f42")
COL_DEV_DARK = QColor("#141f2d")
COL_BD = QColor("#72a6d4")
COL_TXT = QColor("#e2ecf7")
COL_NAME = QColor("#83bdf0")
COL_ALARM = QColor("#ff5c5c")
COL_LEVEL = QColor(47, 150, 110, 160)
COL_BOX_BD = QColor("#33567a")
COL_HIGHLIGHT = QColor(255, 255, 255, 28)


def _valve_rect(cid):
    cx, cy = VALVE_CENTERS[cid]
    return (cx - VS - 4, cy - VS - 4, 2 * VS + 8, 2 * VS + 8)


def _hit_rects():
    """点击区域: 小设备优先"""
    out = []
    for cid in VALVE_CENTERS:
        out.append((cid, QRectF(*_valve_rect(cid))))
    for did, (x, y, w, h) in RECTS.items():
        out.append((did, QRectF(x, y, w, h)))
    out.sort(key=lambda t: t[1].width() * t[1].height())
    return out


class DcsCanvas(QWidget):
    device_clicked = Signal(str)

    ZOOM_MIN, ZOOM_MAX = 0.25, 3.0

    def __init__(self, st, parent=None):
        super().__init__(parent)
        self.st = st
        self._zoom = 1.0
        self.setFixedSize(W, H)
        self._hit = _hit_rects()
        self._phase = 0.0

    # ---------------- 缩放 ----------------
    def zoom(self):
        return self._zoom

    def set_zoom(self, z):
        z = max(self.ZOOM_MIN, min(self.ZOOM_MAX, z))
        if abs(z - self._zoom) < 1e-6:
            return
        self._zoom = z
        self.setFixedSize(int(W * z), int(H * z))
        self.update()

    def fit_zoom(self, view_w, view_h):
        """计算适应可视区所需的缩放比"""
        return max(self.ZOOM_MIN,
                   min(self.ZOOM_MAX, min(view_w / (W + 6), view_h / (H + 6))))

    # ---------------- 交互 ----------------
    def mousePressEvent(self, ev):
        z = self._zoom
        pos = QPointF(ev.position().x() / z, ev.position().y() / z)
        for did, rect in self._hit:
            if rect.contains(pos):
                self.device_clicked.emit(did)
                return
        super().mousePressEvent(ev)

    def advance_anim(self):
        """粒子推进一帧 (固定步长; 仅在系统活动时由外部调用, 暂停/急停/未连接时不调用即冻结)"""
        self._phase += 12.0

    # ---------------- 绘制 ----------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self._zoom, self._zoom)     # 以下全部为逻辑坐标, 布局不变
        # 深色渐变背景
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, QColor("#14202f"))
        bg.setColorAt(1, QColor("#0c131d"))
        p.fillRect(QRectF(0, 0, W, H), QBrush(bg))
        self._draw_grid(p)
        self._draw_pipes(p)
        self._draw_flows(p)
        self._draw_streams_labels(p)
        for did, dtype in [("V101", "tank"), ("V102", "tank"), ("V103", "tank"),
                           ("V104", "tank")]:
            self._draw_tank(p, did)
        self._draw_pump(p, "P101")
        self._draw_pump(p, "P102")
        for did in ("E101", "E102", "E103"):
            self._draw_hex(p, did)
        self._draw_column(p, "T101")
        for cid in VALVE_CENTERS:
            self._draw_valve(p, cid)
        self._draw_title_legend(p)
        self._draw_plc_overlay(p)
        p.end()

    def _draw_grid(self, p):
        p.setPen(QPen(QColor(255, 255, 255, 6), 1))
        for x in range(0, W, 40):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, 40):
            p.drawLine(0, y, W, y)

    def _device_gradient(self, x, y, w, h, c1=COL_DEV, c2=COL_DEV_DARK):
        g = QLinearGradient(x, y, x, y + h)
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        return g

    def _alarm_pen(self, dev, width=3):
        if dev.alarms:
            a = int(120 + 110 * abs(math.sin(time.time() * 3)))
            pen = QPen(QColor(255, 70, 70, a), width)
        else:
            pen = QPen(COL_BD, width)
        return pen

    def _txt(self, p, x, y, s, color=COL_TXT, size=9, center=False, bold=False):
        f = QFont("Microsoft YaHei", size)
        f.setBold(bold)
        p.setFont(f)
        p.setPen(QPen(color))
        if center:
            fm = QFontMetrics(f)
            w = fm.horizontalAdvance(s)
            p.drawText(int(x - w / 2), int(y), s)
        else:
            p.drawText(int(x), int(y), s)

    def _name(self, p, did, cx, y):
        self._txt(p, cx, y, f"{did} {i18n.tr(did)}", COL_NAME, 9, center=True, bold=True)

    def _valbox(self, p, did, cx, y0, lines):
        """设备参数小底框"""
        f = QFont("Microsoft YaHei", 9)
        fm = QFontMetrics(f)
        w = max(fm.horizontalAdvance(s) for s in lines) + 14
        h = 15 * len(lines) + 8
        p.setPen(QPen(COL_BOX_BD, 1))
        p.setBrush(QColor(10, 18, 28, 200))
        p.drawRoundedRect(QRectF(cx - w / 2, y0, w, h), 5, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(120, 190, 240, 30))
        p.drawRoundedRect(QRectF(cx - w / 2, y0, w, 3), 1.5, 1.5)
        for i, s in enumerate(lines):
            self._txt(p, cx, y0 + 16 + i * 15, s, COL_TXT, 9, center=True)

    # ---- 管线与流动 ----
    def _draw_pipes(self, p):
        # 外层管壁
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(COL_PIPE_CASE, 8))
        for _, pts in PIPES:
            for i in range(len(pts) - 1):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[i + 1]))
        # 内层管腔
        p.setPen(QPen(COL_PIPE, 3.2))
        for _, pts in PIPES:
            for i in range(len(pts) - 1):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[i + 1]))

    def _path_point(self, pts, dist):
        acc = 0.0
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            seg = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            if acc + seg >= dist:
                r = (dist - acc) / seg if seg else 0
                return (x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
            acc += seg
        return pts[-1]

    def _path_len(self, pts):
        return sum(((pts[i + 1][0] - pts[i][0]) ** 2 +
                    (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
                   for i in range(len(pts) - 1))

    def _draw_flows(self, p):
        p.setPen(Qt.NoPen)
        for key, paths in FLOW_PATHS.items():
            flow = self.st.flows.get(key, 0.0)
            if flow < 0.02:
                continue
            col = QColor(STREAM_COLOR[key])
            glow = QColor(col)
            glow.setAlpha(60)
            for pts in paths:
                total = self._path_len(pts)
                spacing = 34.0
                off = self._phase * (0.25 + 0.75 * flow) % spacing
                d = off
                while d < total:
                    x, y = self._path_point(pts, d)
                    p.setBrush(QBrush(glow))
                    p.drawEllipse(QPointF(x, y), 5.5, 5.5)
                    p.setBrush(QBrush(col))
                    p.drawEllipse(QPointF(x, y), 2.6, 2.6)
                    d += spacing

    def _stream_label(self, p, x, y, key):
        col = QColor(STREAM_COLOR[key])
        self._txt(p, x, y, i18n.tr(f"stream.{key}"), col, 9, bold=True)

    def _draw_streams_labels(self, p):
        self._stream_label(p, 12, 300, "feed")
        self._stream_label(p, 432, 745, "steam")
        self._stream_label(p, 698, 105, "cooling")
        self._stream_label(p, 1012, 122, "cooling")
        self._stream_label(p, 1452, 258, "distillate")
        self._stream_label(p, 1105, 858, "bottoms")

    # ---- 设备 ----
    def _draw_tank(self, p, did):
        x, y, w, h = RECTS[did]
        dev = self.st.devices[did]
        body = QRectF(x, y + 10, w, h - 20)
        # 罐体渐变填充
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(self._device_gradient(x, y, w, h,
                   QColor("#27415c"), QColor("#14202f"))))
        p.drawRoundedRect(body, 12, 12)
        p.drawEllipse(QRectF(x, y, w, 20))
        # 液位 (裁剪到罐体内, 带垂直渐变 + 液面高光)
        if dev.level > 0:
            lh = (h - 24) * dev.level / 100.0
            lrect = QRectF(x + 2, y + 12 + (h - 24 - lh), w - 4, lh)
            clip = QPainterPath()
            clip.addRoundedRect(body, 12, 12)
            p.save()
            p.setClipPath(clip)
            lg = QLinearGradient(0, lrect.top(), 0, lrect.bottom())
            lg.setColorAt(0, QColor(111, 224, 168, 215))
            lg.setColorAt(1, QColor(26, 110, 78, 215))
            p.fillRect(lrect, QBrush(lg))
            p.setPen(QPen(QColor(190, 250, 220, 220), 2))
            p.drawLine(QPointF(lrect.left() + 6, lrect.top()),
                       QPointF(lrect.right() - 6, lrect.top()))
            p.restore()
        # 玻璃高光条
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(QRectF(x + 10, y + 22, 8, h - 44), 4, 4)
        # 描边 (报警时红色闪烁)
        p.setBrush(Qt.NoBrush)
        p.setPen(self._alarm_pen(dev))
        p.drawRoundedRect(body, 12, 12)
        p.drawEllipse(QRectF(x, y, w, 20))
        cx = x + w / 2
        self._name(p, did, cx, y - 6)
        self._valbox(p, did, cx, y + h / 2 - 24, [
            f"{i18n.tr('field.temp')} {dev.temp:.1f}{i18n.tr('unit.c')}",
            f"{i18n.tr('field.press')} {dev.press:.1f}{i18n.tr('unit.kpa')}",
            f"{i18n.tr('field.level')} {dev.level:.1f}{i18n.tr('unit.pct')}",
        ])

    def _draw_pump(self, p, did):
        x, y, w, h = RECTS[did]
        dev = self.st.devices[did]
        cx, cy = x + w / 2, y + h / 2
        # 运行光晕
        if dev.running:
            halo = QRadialGradient(cx, cy, 54)
            halo.setColorAt(0, QColor(90, 220, 150, 75))
            halo.setColorAt(1, QColor(90, 220, 150, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(cx, cy), 54, 54)
        # 泵体径向渐变
        rg = QRadialGradient(cx - 12, cy - 12, 56)
        if dev.running:
            rg.setColorAt(0, QColor("#3aa872"))
            rg.setColorAt(1, QColor("#10301f"))
        else:
            rg.setColorAt(0, QColor("#33485e"))
            rg.setColorAt(1, QColor("#121b26"))
        p.setBrush(QBrush(rg))
        p.setPen(self._alarm_pen(dev))
        p.drawEllipse(QPointF(cx, cy), 40, 40)
        # 叶轮三角
        col = QColor("#a6f5cb") if dev.running else QColor("#5f7890")
        p.setBrush(QBrush(col))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(cx - 16, cy - 14), QPointF(cx - 16, cy + 14),
                                 QPointF(cx + 20, cy)]))
        self._name(p, did, cx, y - 8)
        self._valbox(p, did, cx, y + h + 4, [
            f"{i18n.tr('field.speed')} {dev.speed:.0f}{i18n.tr('unit.pct')}",
            f"{i18n.tr('field.state')} {i18n.tr('state.on') if dev.running else i18n.tr('state.off')}",
        ])

    def _draw_hex(self, p, did):
        x, y, w, h = RECTS[did]
        dev = self.st.devices[did]
        # 壳体渐变
        p.setPen(Qt.NoPen)
        hot = did in ("E102", "E101")
        g = QLinearGradient(x, y, x, y + h)
        if hot:
            g.setColorAt(0, QColor("#5a4a38"))
            g.setColorAt(1, QColor("#2a241c"))
        else:
            g.setColorAt(0, QColor("#234460"))
            g.setColorAt(1, QColor("#12202e"))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
        # 内部换热符号 (折流板)
        baff = QColor("#7ab8e8"); baff.setAlpha(170)
        p.setPen(QPen(baff, 2))
        step = 14.0
        yy = y + 12
        while yy < y + h - 12:
            p.drawLine(QPointF(x + 10, yy), QPointF(x + w - 10, yy + step / 2))
            yy += step
        # 高光
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(x + 6, y + 5, w - 12, 8), 4, 4)
        # 描边
        p.setBrush(Qt.NoBrush)
        p.setPen(self._alarm_pen(dev))
        p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
        cx = x + w / 2
        self._name(p, did, cx, y - 6)
        lines = [f"{i18n.tr('field.temp')} {dev.temp:.1f}{i18n.tr('unit.c')}",
                 f"{i18n.tr('field.press')} {dev.press:.0f}{i18n.tr('unit.kpa')}"]
        if did == "E101":
            lines.append(f"{i18n.tr('field.power')} {dev.power:.0f}{i18n.tr('unit.pct')}")
        self._valbox(p, did, cx, y + h + 4, lines)

    def _draw_column(self, p, did):
        x, y, w, h = RECTS[did]
        dev = self.st.devices[did]
        rect = QRectF(x, y, w, h)
        # 塔体渐变
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(self._device_gradient(x, y, w, h,
                   QColor("#2a4460"), QColor("#111a26"))))
        p.drawRoundedRect(rect, 16, 16)
        # 塔釜加热辉光 (随蒸汽阀开度)
        steam = self.st.devices["FV102"].opening / 100.0
        if steam > 0.05:
            glow = QRadialGradient(x + w / 2, y + h - 20, 150)
            glow.setColorAt(0, QColor(230, 130, 60, int(70 * steam)))
            glow.setColorAt(1, QColor(230, 130, 60, 0))
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(x + w / 2, y + h - 20), 150, 90)
        # 塔板
        p.setPen(QPen(QColor(122, 184, 232, 110), 1.5))
        yy = y + 36
        while yy < y + h - 30:
            p.drawLine(QPointF(x + 8, yy), QPointF(x + w - 8, yy))
            yy += 30
        # 高光条
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 16))
        p.drawRoundedRect(QRectF(x + 8, y + 18, 7, h - 40), 4, 4)
        # 描边
        p.setBrush(Qt.NoBrush)
        p.setPen(self._alarm_pen(dev))
        p.drawRoundedRect(rect, 16, 16)
        cx = x + w / 2
        self._name(p, did, cx, y - 8)
        # 塔顶温度 = T101温度; 塔釜温度 = E102温度
        self._txt(p, x + 10, y + 24,
                  f"{i18n.tr('field.top_temp')} {dev.temp:.1f}{i18n.tr('unit.c')}",
                  COL_TXT, 9, bold=True)
        self._txt(p, x + 10, y + h / 2,
                  f"{i18n.tr('field.press')} {dev.press:.1f}{i18n.tr('unit.kpa')}",
                  COL_TXT, 9, bold=True)
        e102 = self.st.devices.get("E102")
        bot = e102.temp if e102 is not None else dev.temp
        self._txt(p, x + 10, y + h - 10,
                  f"{i18n.tr('field.bot_temp')} {bot:.1f}{i18n.tr('unit.c')}",
                  COL_TXT, 9, bold=True)

    def _draw_valve(self, p, cid):
        cx, cy = VALVE_CENTERS[cid]
        dev = self.st.devices[cid]
        op = dev.opening / 100.0
        # 开度光晕
        if op > 0.05:
            glow = QRadialGradient(cx, cy, 30)
            glow.setColorAt(0, QColor(240, 180, 80, int(80 * op)))
            glow.setColorAt(1, QColor(240, 180, 80, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(cx, cy), 30, 30)
        c1 = QColor("#e0a845")
        c2 = QColor("#2a3a4c")
        col = QColor(int(c2.red() + (c1.red() - c2.red()) * op),
                     int(c2.green() + (c1.green() - c2.green()) * op),
                     int(c2.blue() + (c1.blue() - c2.blue()) * op))
        # 阀柄
        p.setPen(QPen(QColor("#8fa7c0"), 2.5))
        p.drawLine(QPointF(cx, cy - VS), QPointF(cx, cy - VS - 6))
        p.setBrush(QBrush(col))
        p.setPen(self._alarm_pen(dev, 2))
        p.drawPolygon(QPolygonF([QPointF(cx - VS, cy - VS), QPointF(cx - VS, cy + VS),
                                 QPointF(cx, cy)]))
        p.drawPolygon(QPolygonF([QPointF(cx + VS, cy - VS), QPointF(cx + VS, cy + VS),
                                 QPointF(cx, cy)]))
        p.setBrush(QBrush(QColor("#f0d8a0")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 2.6, 2.6)
        self._name(p, cid, cx, cy - VS - 10)
        self._txt(p, cx, cy + VS + 16, f"{dev.opening:.0f}{i18n.tr('unit.pct')}",
                  QColor("#f0cf82"), 9, center=True, bold=True)

    def _draw_title_legend(self, p):
        self._txt(p, 40, 50, i18n.tr("title.dcs"), QColor("#dceafc"), 13, bold=True)
        lx, ly = 40, 620
        bw, bh = 190, 30 + 22 * len(LEGEND)
        # 面板渐变 + 描边
        g = QLinearGradient(lx, ly, lx, ly + bh)
        g.setColorAt(0, QColor(28, 42, 58, 225))
        g.setColorAt(1, QColor(14, 22, 32, 225))
        p.setPen(QPen(QColor("#3a5a7e"), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(lx, ly, bw, bh), 7, 7)
        self._txt(p, lx + 12, ly + 20, "LEGEND", QColor("#9fc8ef"), 9, bold=True)
        for i, key in enumerate(LEGEND):
            yy = ly + 38 + i * 22
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(STREAM_COLOR[key]))
            p.drawEllipse(QPointF(lx + 24, yy - 4), 4, 4)
            p.setPen(QPen(QColor(STREAM_COLOR[key]), 3))
            p.drawLine(lx + 34, yy - 4, lx + 50, yy - 4)
            self._txt(p, lx + 60, yy, i18n.tr(f"stream.{key}"), COL_TXT, 9)

    def _draw_plc_overlay(self, p):
        """PLC 模式: 仅在未连接时绘制静止遮罩+提示横幅; 连接成功后不遮挡画面"""
        if self.st.mode != "plc":
            return
        if getattr(self.st, "plc_connected", False):
            return
        cx = W / 2
        # 静止遮罩 + 提示横幅 (两行, 自动宽度, 不裁剪)
        p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, 90))
        text = i18n.tr("plc.waiting")
        bg = QColor(150, 60, 40, 235)
        lines = text.count("\n") + 1
        f = QFont("Microsoft YaHei", 12)
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        max_line = max(text.split("\n"), key=lambda s: fm.horizontalAdvance(s))
        w = fm.horizontalAdvance(max_line) + 80
        h = 34 * lines + 22
        rect = QRectF(cx - w / 2, 64, w, h)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1.5))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 8, 8)
        p.setPen(QPen(QColor("#ffffff")))
        p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, text)
