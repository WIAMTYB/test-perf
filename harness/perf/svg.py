"""Inline SVG line charts for the dossier: no JavaScript, deterministic output, prints well."""
from __future__ import annotations

from datetime import datetime
from html import escape

PALETTE = ["#1f5f8b", "#d9822b", "#2e8b57", "#8b2e5f", "#5f5f5f", "#b8860b", "#4682b4", "#a0522d"]


def line_chart(title: str, series: dict[str, list[tuple[datetime, float]]], unit: str = "",
               width: int = 900, height: int = 260, y_min: float | None = 0.0) -> str:
    """series: name -> [(timestamp, value)], timestamps ascending."""
    points = [(t, v) for values in series.values() for t, v in values if v == v]  # drop NaN
    if not points:
        return f'<div class="chart empty"><h4>{escape(title)}</h4><p>aucune donnée</p></div>'
    left, right, top, bottom = 60, 20, 30, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    t0 = min(t for t, _ in points)
    t1 = max(t for t, _ in points)
    span = max((t1 - t0).total_seconds(), 1.0)
    lo = min(v for _, v in points) if y_min is None else min(y_min, min(v for _, v in points))
    hi = max(v for _, v in points)
    if hi <= lo:
        hi = lo + 1.0
    hi = _nice_ceiling(hi)

    def x(t: datetime) -> float:
        return left + (t - t0).total_seconds() / span * plot_w

    def y(v: float) -> float:
        return top + plot_h - (v - lo) / (hi - lo) * plot_h

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(title)}">',
             f'<text x="{left}" y="18" class="chart-title">{escape(title)}</text>']
    # horizontal grid, 4 bands
    for i in range(5):
        value = lo + (hi - lo) * i / 4
        yy = y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 6}" y="{yy + 4:.1f}" class="axis" text-anchor="end">{_fmt(value)}{escape(unit)}</text>')
    # time axis, 5 ticks
    for i in range(6):
        t = t0 + (t1 - t0) * i / 5
        xx = x(t)
        parts.append(f'<line x1="{xx:.1f}" y1="{top + plot_h}" x2="{xx:.1f}" y2="{top + plot_h + 4}" class="grid"/>')
        parts.append(f'<text x="{xx:.1f}" y="{top + plot_h + 16}" class="axis" text-anchor="middle">{t:%H:%M:%S}</text>')
    for index, (name, values) in enumerate(series.items()):
        clean = [(t, v) for t, v in values if v == v]
        if not clean:
            continue
        color = PALETTE[index % len(PALETTE)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(v):.1f}" for i, (t, v) in enumerate(clean))
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6"/>')
        parts.append(f'<rect x="{left + 10 + index * 160}" y="{height - 12}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{left + 24 + index * 160}" y="{height - 3}" class="legend">{escape(name)[:22]}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _nice_ceiling(value: float) -> float:
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for factor in (1, 2, 2.5, 5, 10):
        if value <= magnitude * factor:
            return magnitude * factor
    return value


def _fmt(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value / 1000:.1f}k"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")
