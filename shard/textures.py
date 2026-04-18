"""Procedural HQ "shattered glass" overlay texture.

Generated at runtime with QPainter so there is no binary asset to ship.
Returns a single ``QPixmap`` that should be painted on top of the window
background at low opacity to give the glass a fractured, refractive feel.

The texture combines:
  * Several "impact" points with radial cracks branching outward.
  * Concentric polygonal shock-rings around each impact.
  * Secondary branching cracks (each with its own forks).
  * A handful of bright micro-glints scattered across the surface.
  * A very faint vignette so the cracks read as glass, not as a wireframe.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)


def _crack(painter: QPainter, start: QPointF, angle: float, length: float,
           rng: random.Random, depth: int = 0) -> None:
    """Draw a jagged crack of ``length`` from ``start`` at ``angle``.

    Each crack is a sequence of short segments with small angular jitter,
    drawn with two stacked pens (a soft halo and a crisp white core) for a
    subtle refractive look. With some probability spawns a forked sub-crack.
    """
    seg_count = max(4, int(length / 14))
    seg_len = length / seg_count
    points = [start]
    a = angle
    p = QPointF(start)
    for i in range(seg_count):
        a += rng.uniform(-0.22, 0.22)
        # taper slightly toward the end
        t = i / seg_count
        sl = seg_len * (1.0 - 0.35 * t)
        p = QPointF(p.x() + math.cos(a) * sl, p.y() + math.sin(a) * sl)
        points.append(p)

    path = QPainterPath(points[0])
    for pt in points[1:]:
        path.lineTo(pt)

    # halo
    halo = QPen(QColor(180, 220, 255, 38), 2.4)
    halo.setCapStyle(Qt.RoundCap)
    halo.setJoinStyle(Qt.RoundJoin)
    painter.setPen(halo)
    painter.drawPath(path)
    # core
    core = QPen(QColor(255, 255, 255, 110), 0.9)
    core.setCapStyle(Qt.RoundCap)
    painter.setPen(core)
    painter.drawPath(path)

    # branches
    if depth < 2 and seg_count >= 4:
        for i in range(1, seg_count - 1):
            if rng.random() < (0.35 if depth == 0 else 0.18):
                branch_angle = a + rng.choice((-1, 1)) * rng.uniform(0.6, 1.2)
                branch_len = length * rng.uniform(0.25, 0.55)
                _crack(painter, points[i], branch_angle, branch_len, rng, depth + 1)


def _ring(painter: QPainter, center: QPointF, radius: float, rng: random.Random) -> None:
    """Irregular polygonal shock ring."""
    sides = rng.randint(9, 14)
    pts: list[QPointF] = []
    for i in range(sides):
        ang = 2 * math.pi * i / sides + rng.uniform(-0.15, 0.15)
        r = radius * rng.uniform(0.82, 1.18)
        pts.append(QPointF(center.x() + math.cos(ang) * r,
                           center.y() + math.sin(ang) * r))
    path = QPainterPath(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    pen = QPen(QColor(200, 230, 255, 30), 1.0)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)


def _impact(painter: QPainter, center: QPointF, max_len: float, rng: random.Random) -> None:
    """A radial impact: bright glint, several rings, many radial cracks."""
    # Bright soft glint at the impact point.
    glow = QRadialGradient(center, max_len * 0.18)
    glow.setColorAt(0.0, QColor(255, 255, 255, 120))
    glow.setColorAt(0.4, QColor(180, 220, 255, 40))
    glow.setColorAt(1.0, QColor(180, 220, 255, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(glow))
    painter.drawEllipse(center, max_len * 0.18, max_len * 0.18)

    # Concentric rings.
    for i in range(rng.randint(2, 4)):
        _ring(painter, center, max_len * (0.18 + 0.18 * (i + 1)), rng)

    # Radial cracks.
    n = rng.randint(9, 14)
    base = rng.uniform(0, math.tau)
    for i in range(n):
        ang = base + (math.tau * i / n) + rng.uniform(-0.1, 0.1)
        length = max_len * rng.uniform(0.55, 1.0)
        start = QPointF(
            center.x() + math.cos(ang) * max_len * 0.04,
            center.y() + math.sin(ang) * max_len * 0.04,
        )
        _crack(painter, start, ang, length, rng)


def _micro_glints(painter: QPainter, w: int, h: int, rng: random.Random) -> None:
    """Tiny specular sparkles scattered across the surface."""
    painter.setPen(Qt.NoPen)
    for _ in range(80):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        r = rng.uniform(0.4, 1.6)
        a = rng.randint(40, 130)
        painter.setBrush(QColor(255, 255, 255, a))
        painter.drawEllipse(QPointF(x, y), r, r)


def _hairlines(painter: QPainter, w: int, h: int, rng: random.Random) -> None:
    """Sparse long hairline fissures across the whole pane."""
    for _ in range(rng.randint(6, 10)):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h)
        ang = rng.uniform(0, math.tau)
        _crack(painter, QPointF(x, y), ang, rng.uniform(w * 0.25, w * 0.55), rng)


@lru_cache(maxsize=4)
def shattered_glass_pixmap(width: int, height: int, seed: int = 7) -> QPixmap:
    """Return a cached procedural shattered-glass overlay pixmap."""
    rng = random.Random(seed)
    pm = QPixmap(width, height)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    # Faint cool wash so the texture has body, not just lines.
    wash = QLinearGradient(0, 0, width, height)
    wash.setColorAt(0.0, QColor(180, 220, 255, 8))
    wash.setColorAt(0.5, QColor(120, 160, 240, 4))
    wash.setColorAt(1.0, QColor(160, 120, 240, 8))
    p.fillRect(QRectF(0, 0, width, height), wash)

    # Two or three impact points placed pseudo-randomly inside the pane.
    impacts = []
    for _ in range(rng.randint(2, 3)):
        impacts.append(QPointF(rng.uniform(width * 0.15, width * 0.85),
                               rng.uniform(height * 0.15, height * 0.85)))
    max_len = math.hypot(width, height) * 0.45
    for c in impacts:
        _impact(p, c, max_len, rng)

    _hairlines(p, width, height, rng)
    _micro_glints(p, width, height, rng)

    # Soft inner vignette to push the cracks toward the edges.
    vg = QRadialGradient(QPointF(width * 0.5, height * 0.45),
                         max(width, height) * 0.7)
    vg.setColorAt(0.0, QColor(0, 0, 0, 0))
    vg.setColorAt(0.85, QColor(0, 0, 0, 28))
    vg.setColorAt(1.0, QColor(0, 0, 0, 60))
    p.fillRect(QRectF(0, 0, width, height), vg)

    p.end()
    return pm
