"""Custom-drawn 3D Shard logo widget."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class ShardLogo(QWidget):
    """A faceted crystal "shard" rendered in pure QPainter, with depth."""

    def __init__(self, parent: QWidget | None = None, size: int = 30) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        cx, cy = r.center().x(), r.center().y()
        w, h = r.width(), r.height()

        # Outer outline.
        top = QPointF(cx, r.top())
        upper_l = QPointF(r.left() + w * 0.18, r.top() + h * 0.30)
        upper_r = QPointF(r.right() - w * 0.18, r.top() + h * 0.30)
        mid_l = QPointF(r.left(), cy + h * 0.04)
        mid_r = QPointF(r.right(), cy + h * 0.04)
        bottom = QPointF(cx, r.bottom())
        # Internal table-edge points (the "table" of the gem).
        tbl_l = QPointF(cx - w * 0.18, r.top() + h * 0.30)
        tbl_r = QPointF(cx + w * 0.18, r.top() + h * 0.30)
        belt_l = QPointF(cx - w * 0.22, cy + h * 0.05)
        belt_r = QPointF(cx + w * 0.22, cy + h * 0.05)

        outline = QPainterPath()
        outline.moveTo(top)
        outline.lineTo(upper_r)
        outline.lineTo(mid_r)
        outline.lineTo(bottom)
        outline.lineTo(mid_l)
        outline.lineTo(upper_l)
        outline.closeSubpath()

        # Soft outer glow.
        glow = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.7)
        glow.setColorAt(0.0, QColor(140, 200, 255, 70))
        glow.setColorAt(1.0, QColor(140, 200, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), w * 0.7, h * 0.7)

        # Base body fill.
        body = QLinearGradient(QPointF(cx, r.top()), QPointF(cx, r.bottom()))
        body.setColorAt(0.0, QColor(200, 245, 255, 235))
        body.setColorAt(0.45, QColor(120, 180, 255, 230))
        body.setColorAt(1.0, QColor(120, 80, 220, 235))
        p.setBrush(QBrush(body))
        p.setPen(QPen(QColor(230, 245, 255, 220), 1.2))
        p.drawPath(outline)

        # ---- Faceting (each facet has its own gradient for a 3D look) ----
        def facet(points: list[QPointF], grad: QLinearGradient) -> None:
            path = QPainterPath(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawPath(path)

        # Crown left (bright)
        g = QLinearGradient(top, mid_l)
        g.setColorAt(0.0, QColor(255, 255, 255, 180))
        g.setColorAt(1.0, QColor(160, 210, 255, 90))
        facet([top, tbl_l, belt_l, mid_l, upper_l], g)

        # Crown right (mid)
        g = QLinearGradient(top, mid_r)
        g.setColorAt(0.0, QColor(190, 225, 255, 150))
        g.setColorAt(1.0, QColor(110, 150, 230, 80))
        facet([top, upper_r, mid_r, belt_r, tbl_r], g)

        # Center table (vertical sliver)
        g = QLinearGradient(QPointF(cx, r.top()), QPointF(cx, cy))
        g.setColorAt(0.0, QColor(255, 255, 255, 220))
        g.setColorAt(1.0, QColor(180, 220, 255, 60))
        facet([top, tbl_r, belt_r, belt_l, tbl_l], g)

        # Pavilion left (dark)
        g = QLinearGradient(belt_l, bottom)
        g.setColorAt(0.0, QColor(110, 130, 220, 150))
        g.setColorAt(1.0, QColor(60, 30, 110, 220))
        facet([mid_l, belt_l, bottom], g)

        # Pavilion right (mid-dark)
        g = QLinearGradient(belt_r, bottom)
        g.setColorAt(0.0, QColor(140, 150, 230, 130))
        g.setColorAt(1.0, QColor(80, 50, 150, 210))
        facet([mid_r, belt_r, bottom], g)

        # Pavilion center (deep)
        g = QLinearGradient(QPointF(cx, cy), bottom)
        g.setColorAt(0.0, QColor(150, 180, 255, 180))
        g.setColorAt(1.0, QColor(40, 20, 90, 230))
        facet([belt_l, belt_r, bottom], g)

        # Bright crisp facet edges
        edge = QPen(QColor(255, 255, 255, 130), 0.9)
        p.setPen(edge)
        p.setBrush(Qt.NoBrush)
        for a, b in (
            (top, mid_l), (top, mid_r),
            (upper_l, bottom), (upper_r, bottom),
            (tbl_l, belt_l), (tbl_r, belt_r),
            (belt_l, belt_r),
        ):
            p.drawLine(a, b)

        # Specular highlight: small bright streak near the upper-left facet.
        spec = QPainterPath()
        spec.moveTo(QPointF(cx - w * 0.04, r.top() + h * 0.06))
        spec.lineTo(QPointF(cx - w * 0.16, r.top() + h * 0.26))
        spec.lineTo(QPointF(cx - w * 0.10, r.top() + h * 0.28))
        spec.lineTo(QPointF(cx - w * 0.02, r.top() + h * 0.10))
        spec.closeSubpath()
        p.fillPath(spec, QColor(255, 255, 255, 180))

        # Outline again on top for crispness
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(outline)

        p.end()
