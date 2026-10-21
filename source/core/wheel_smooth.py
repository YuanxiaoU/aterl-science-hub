# -*- coding: utf-8 -*-
"""鼠标滚轮线性化工具:
1) QListWidget / QTableWidget 等 ItemView 改为按像素平滑滚动 (默认按项跳),
   视觉上"一滚一格"变成平滑线性滑动;
2) QComboBox / QSpinBox / QDoubleSpinBox 在未获焦点时, 滚轮不改变自身值/选项,
   而是滚动最近的祖先滚动区 (避免想滚页面时数值突然跳变);
   已聚焦的控件仍可用滚轮改值 (符合常见工业软件习惯)。
使用: 在 main() 里 app.installEventFilter(WheelSmoother())
"""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import (QApplication, QComboBox, QAbstractSpinBox,
                               QAbstractItemView, QAbstractScrollArea,
                               QScrollArea)


class WheelSmoother(QObject):
    def eventFilter(self, obj, event):
        if event.type() != QEvent.Wheel:
            return False

        w = obj
        # 滚轮实际由 viewport 接收, 沿 parent 找到真正的控件
        real = w
        while real is not None and not isinstance(real, (QComboBox, QAbstractSpinBox,
                                                         QAbstractItemView,
                                                         QAbstractScrollArea)):
            real = real.parentWidget()
        w = real if real is not None else w

        # 首次遇到 ItemView 时改为像素平滑滚动 (默认 ScrollPerItem 会按格跳)
        if isinstance(w, QAbstractItemView):
            if w.verticalScrollMode() != QAbstractItemView.ScrollPerPixel:
                w.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            # 横向也像素化
            if w.horizontalScrollMode() != QAbstractItemView.ScrollPerPixel:
                w.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
            return False            # 让 ItemView 自己处理像素滚动

        # QScrollArea (如 DCS 工艺画布): 手动按固定像素滚动, 避免 Qt 默认
        # 步长随内容尺寸放大导致一滚就到顶/底
        if isinstance(w, QScrollArea) and not isinstance(w, QAbstractItemView):
            vbar = w.verticalScrollBar()
            hbar = w.horizontalScrollBar()
            ad = event.angleDelta()
            if ad.y() != 0:
                step = max(1, min(vbar.singleStep(), 40)) * 3
                vbar.setValue(vbar.value() - (step if ad.y() > 0 else -step))
            if ad.x() != 0:
                step = max(1, min(hbar.singleStep(), 40)) * 3
                hbar.setValue(hbar.value() - (step if ad.x() > 0 else -step))
            return True

        # 下拉框 / 数值框: 滚轮一律不改变自身值/选项, 改滚最近的祖先滚动区
        # (要改值请点击输入或用上下箭头, 避免想滚页面时数值突然跳变)
        if isinstance(w, (QComboBox, QAbstractSpinBox)):
            target = self._find_scroll_ancestor(w)
            if target is not None:
                bar = target.verticalScrollBar()
                delta = event.angleDelta().y()
                # 一次滚轮约 120 度 -> 3 个 singleStep, 线性平滑
                step = max(1, bar.singleStep()) * 3
                if delta > 0:
                    bar.setValue(bar.value() - step)
                elif delta < 0:
                    bar.setValue(bar.value() + step)
            return True             # 已处理, 不再让控件改值

        return False

    @staticmethod
    def _find_scroll_ancestor(widget):
        p = widget.parentWidget()
        while p is not None:
            if isinstance(p, QAbstractScrollArea):
                return p
            p = p.parentWidget()
        return None
