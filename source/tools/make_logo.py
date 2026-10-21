# -*- coding: utf-8 -*-
"""
Aterl-DistSim Logo 生成器
使用 QPainter 程序化绘制精馏主题矢量图标 (与 DCS 深色主题一致),
输出:
  assets/logo.png   512x512 高清位图
  assets/logo.ico   多尺寸 Windows 图标 (供 PyInstaller)
  ui/logo_asset.py  内嵌 base64 (供运行时关于对话框/窗口图标, onefile 免路径)
"""
import os
import sys
import base64

# 注意: 需要真实平台后端以获得完整字体渲染 (offscreen 缺字库会出现豆腐块)
# 仅在无显示环境时回退 offscreen
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QImage, QPainter, QColor, QPen, QBrush, QFont,
                           QLinearGradient, QRadialGradient, QPainterPath, QPixmap,
                           QPolygonF)
from PySide6.QtWidgets import QApplication

# 字体引擎/图像绘制需要 QGuiApplication 先存在
_app = QApplication.instance() or QApplication([])

S = 512
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")


def draw_logo(img):
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    # ---------- 背景: 圆角方块 + 深蓝纵向渐变 ----------
    bg = QLinearGradient(0, 0, 0, S)
    bg.setColorAt(0.0, QColor("#1a2b44"))
    bg.setColorAt(0.55, QColor("#111d2e"))
    bg.setColorAt(1.0, QColor("#0a121d"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(bg))
    p.drawRoundedRect(QRectF(8, 8, S - 16, S - 16), 96, 96)

    # 背景网格点缀 (呼应 DCS 画布)
    p.setPen(QPen(QColor(255, 255, 255, 7), 1))
    for g in range(72, S - 40, 64):
        p.drawLine(40, g, S - 40, g)
        p.drawLine(g, 40, g, S - 40)

    # 边框
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#3f6d9c"), 3))
    p.drawRoundedRect(QRectF(8, 8, S - 16, S - 16), 96, 96)

    # ---------- 精馏塔 ----------
    cx = S / 2
    tx, ty, tw, th = 216.0, 118.0, 80.0, 262.0
    col_rect = QRectF(tx, ty, tw, th)

    # 塔后青色光晕
    halo = QRadialGradient(cx, ty + th / 2, 210)
    halo.setColorAt(0, QColor(90, 180, 230, 85))
    halo.setColorAt(1, QColor(90, 180, 230, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(halo))
    p.drawEllipse(QPointF(cx, ty + th / 2), 210, 210)

    # 塔体金属渐变
    cg = QLinearGradient(tx, 0, tx + tw, 0)
    cg.setColorAt(0.0, QColor("#16263a"))
    cg.setColorAt(0.25, QColor("#3a5d84"))
    cg.setColorAt(0.55, QColor("#5b88b4"))
    cg.setColorAt(0.8, QColor("#2c4a6b"))
    cg.setColorAt(1.0, QColor("#132233"))
    p.setBrush(QBrush(cg))
    p.setPen(QPen(QColor("#8fc0ea"), 3))
    p.drawRoundedRect(col_rect, 26, 26)

    # 塔顶封头 (椭圆)
    p.setBrush(QBrush(cg))
    p.setPen(QPen(QColor("#8fc0ea"), 3))
    p.drawEllipse(QRectF(tx, ty - 14, tw, 30))

    # 塔板
    p.setPen(QPen(QColor(190, 224, 250, 115), 2))
    for i in range(1, 6):
        yy = ty + 22 + i * 38
        p.drawLine(QPointF(tx + 9, yy), QPointF(tx + tw - 9, yy))

    # 塔内液体 (塔釜) 渐变
    pool = QRectF(tx + 4, ty + th - 86, tw - 8, 82)
    clip = QPainterPath()
    clip.addRoundedRect(col_rect, 26, 26)
    p.save()
    p.setClipPath(clip)
    lg = QLinearGradient(0, pool.top(), 0, pool.bottom())
    lg.setColorAt(0, QColor(120, 230, 180, 220))
    lg.setColorAt(1, QColor(24, 110, 86, 220))
    p.fillRect(pool, QBrush(lg))
    # 液面高光
    p.setPen(QPen(QColor(200, 250, 225, 230), 3))
    p.drawLine(QPointF(pool.left() + 8, pool.top()),
               QPointF(pool.right() - 8, pool.top()))
    # 上升气泡 (蒸气)
    bubbles = [(0.30, 0.62, 7), (0.62, 0.55, 5), (0.45, 0.45, 9),
               (0.70, 0.38, 6), (0.33, 0.30, 5), (0.58, 0.22, 8),
               (0.40, 0.14, 5), (0.66, 0.12, 4)]
    p.setPen(Qt.NoPen)
    for fx, fy, r in bubbles:
        bx = tx + tw * fx
        by = ty + th * fy
        p.setBrush(QColor(210, 240, 255, 150))
        p.drawEllipse(QPointF(bx, by), r, r)
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(QPointF(bx - r * 0.3, by - r * 0.3), r * 0.35, r * 0.35)
    p.restore()

    # 玻璃高光条
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 35))
    p.drawRoundedRect(QRectF(tx + 13, ty + 22, 9, th - 46), 5, 5)

    # ---------- 塔釜再沸器加热辉光 ----------
    rg = QRadialGradient(cx, ty + th - 12, 120)
    rg.setColorAt(0, QColor(240, 150, 60, 150))
    rg.setColorAt(1, QColor(240, 150, 60, 0))
    p.setBrush(QBrush(rg))
    p.drawEllipse(QPointF(cx, ty + th - 8), 120, 70)

    # ---------- 管线 (呼应 DCS 双层管) ----------
    # 进料管 (左侧, 塔中部)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#1c3349"), 12))
    p.drawLine(QPointF(60, ty + 150), QPointF(tx - 2, ty + 150))
    p.setPen(QPen(QColor("#5b8fc0"), 5))
    p.drawLine(QPointF(60, ty + 150), QPointF(tx - 2, ty + 150))
    # 塔顶产品管 (右上)
    p.setPen(QPen(QColor("#1c3349"), 12))
    p.drawLine(QPointF(tx + tw + 2, ty + 26), QPointF(430, ty + 26))
    p.drawLine(QPointF(430, ty + 26), QPointF(430, 84))
    p.setPen(QPen(QColor("#69a8d8"), 5))
    p.drawLine(QPointF(tx + tw + 2, ty + 26), QPointF(430, ty + 26))
    p.drawLine(QPointF(430, ty + 26), QPointF(430, 84))
    # 冷凝器 (右上小鼓)
    p.setPen(QPen(QColor("#8fc0ea"), 3))
    p.setBrush(QBrush(QLinearGradient(404, 60, 456, 108)))
    cond = QRectF(402, 60, 56, 44)
    cg2 = QLinearGradient(402, 60, 402, 104)
    cg2.setColorAt(0, QColor("#2b5a86"))
    cg2.setColorAt(1, QColor("#14283e"))
    p.setBrush(QBrush(cg2))
    p.drawRoundedRect(cond, 10, 10)
    # 塔釜采出管 (右下)
    p.setPen(QPen(QColor("#1c3349"), 12))
    p.drawLine(QPointF(tx + tw + 2, ty + th - 40), QPointF(452, ty + th - 40))
    p.setPen(QPen(QColor("#e0a845"), 5))
    p.drawLine(QPointF(tx + tw + 2, ty + th - 40), QPointF(452, ty + th - 40))

    # 进料阀门 (左侧管上小菱形)
    vx, vy = 128.0, ty + 150
    p.setPen(QPen(QColor("#f0c878"), 2.5))
    p.setBrush(QBrush(QColor("#e0a845")))
    p.drawPolygon(QPolygonF([QPointF(vx - 12, vy - 10), QPointF(vx, vy), QPointF(vx - 12, vy + 10)]))
    p.drawPolygon(QPolygonF([QPointF(vx + 12, vy - 10), QPointF(vx, vy), QPointF(vx + 12, vy + 10)]))

    # ---------- 塔顶上升蒸气泡 ----------
    p.setPen(Qt.NoPen)
    for bx, by, r in [(cx - 30, 88, 8), (cx + 6, 70, 10), (cx + 34, 92, 6)]:
        p.setBrush(QColor(170, 220, 250, 120))
        p.drawEllipse(QPointF(bx, by), r, r)

    # ---------- 底部文字 ----------
    p.setPen(QColor("#cfe4f7"))
    f = QFont("Microsoft YaHei", 38, QFont.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, 392, S, 56), Qt.AlignHCenter | Qt.AlignTop, "Aterl")
    f2 = QFont("Microsoft YaHei", 22, QFont.DemiBold)
    p.setFont(f2)
    p.setPen(QColor("#7fb4e0"))
    p.drawText(QRectF(0, 442, S, 36), Qt.AlignHCenter | Qt.AlignTop, "DistSim")

    p.end()


def main():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(UI_DIR, exist_ok=True)

    img = QImage(S, S, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    draw_logo(img)

    png_path = os.path.join(ASSETS, "logo.png")
    img.save(png_path, "PNG")
    print("saved:", png_path)

    # ICO (多尺寸, 直接由 Pillow 从 PNG 缩放)
    try:
        from PIL import Image as PILImage
        base = PILImage.open(png_path).convert("RGBA")
        ico_path = os.path.join(ASSETS, "logo.ico")
        base.save(ico_path, format="ICO",
                  sizes=[(s, s) for s in (256, 128, 64, 48, 32, 24, 16)])
        print("saved:", ico_path)
    except Exception as e:
        print("ICO generation failed:", e)

    # 内嵌 base64 模块
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    asset_path = os.path.join(UI_DIR, "logo_asset.py")
    with open(asset_path, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write('"""Aterl-DistSim logo (auto-generated by tools/make_logo.py)."""\n')
        f.write("import base64\n\n")
        f.write("LOGO_PNG_B64 = (\n")
        for i in range(0, len(b64), 76):
            f.write(f'    "{b64[i:i+76]}"\n')
        f.write(")\n\n")
        f.write("def logo_png_bytes():\n    return base64.b64decode(LOGO_PNG_B64)\n")
    print("saved:", asset_path)


if __name__ == "__main__":
    main()
