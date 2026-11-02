"""Minimal SVG plotting (no plotting library is allowed in the venv); PNGs via rsvg-convert.

Supports line, scatter, box, horizontal reference lines, error bars, categorical x ticks and a legend.
"""
import html
import math
import os
import subprocess

PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"]
INK, MUTED, GRID = "#111827", "#4b5563", "#e5e7eb"


def nice_ticks(lo, hi, n=6):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=10 * mag)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 1e-9:
        if t >= lo - step * 1e-9:
            ticks.append(round(t, 10))
        t += step
    return ticks


def fmt_tick(v):
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:g}"


class Plot:
    def __init__(self, title, xlabel, ylabel, width=900, height=560, subtitle=None):
        self.title, self.subtitle, self.xlabel, self.ylabel = title, subtitle, xlabel, ylabel
        self.w, self.h = width, height
        self.m = dict(l=90, r=30, t=70 if subtitle else 56, b=80)
        self.items, self.legend = [], []
        self.xcats = None
        self.xlim = self.ylim = None

    # ----------------------------------------------------------- data
    def categorical_x(self, labels):
        self.xcats = list(labels)

    def line(self, x, y, label=None, color=None, dash=None, width=2.2, marker=False):
        self._add("line", x=list(x), y=list(y), label=label, color=color, dash=dash, width=width, marker=marker)

    def scatter(self, x, y, label=None, color=None, r=2.2, opacity=0.5):
        self._add("scatter", x=list(x), y=list(y), label=label, color=color, r=r, opacity=opacity)

    def boxes(self, positions, stats, label=None, color=None, width=0.5):
        """stats: list of dicts with p5, q1, med, q3, p95."""
        self._add("box", x=list(positions), stats=stats, label=label, color=color, bw=width)

    def errorbars(self, x, y, lo, hi, label=None, color=None):
        self._add("err", x=list(x), y=list(y), lo=list(lo), hi=list(hi), label=label, color=color)

    def hline(self, y, label=None, color=MUTED, dash="6,4", side="right"):
        self._add("hline", y=y, label=label, color=color, dash=dash, side=side)

    def _add(self, kind, **kw):
        if kw.get("color") is None:
            kw["color"] = PALETTE[len([i for i in self.items if i.get("label")]) % len(PALETTE)]
        kw["kind"] = kind
        self.items.append(kw)

    # ----------------------------------------------------------- render
    def _limits(self):
        xs, ys = [], []
        for it in self.items:
            if it["kind"] == "hline":
                ys.append(it["y"])
                continue
            xs += it["x"]
            if it["kind"] == "box":
                ys += [s["p5"] for s in it["stats"]] + [s["p95"] for s in it["stats"]]
            elif it["kind"] == "err":
                ys += it["lo"] + it["hi"]
            else:
                ys += it["y"]
        ys = [v for v in ys if v is not None and math.isfinite(v)]
        xs = [v for v in xs if v is not None and math.isfinite(v)]
        if self.xcats is not None:
            xlo, xhi = -0.6, len(self.xcats) - 0.4
        else:
            pad = (max(xs) - min(xs)) * 0.03 or 1
            xlo, xhi = min(xs) - pad, max(xs) + pad
        pad = (max(ys) - min(ys)) * 0.06 or abs(max(ys)) * 0.05 or 1
        return self.xlim or (xlo, xhi), self.ylim or (min(ys) - pad, max(ys) + pad)

    def svg(self):
        (x0, x1), (y0, y1) = self._limits()
        L, R, T, B = self.m["l"], self.w - self.m["r"], self.m["t"], self.h - self.m["b"]
        sx = lambda v: L + (v - x0) / (x1 - x0) * (R - L)  # noqa: E731
        sy = lambda v: B - (v - y0) / (y1 - y0) * (B - T)  # noqa: E731
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
             f'font-family="Helvetica, Arial, sans-serif">',
             f'<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{L}" y="28" font-size="20" font-weight="bold" fill="{INK}">{html.escape(self.title)}</text>']
        if self.subtitle:
            o.append(f'<text x="{L}" y="50" font-size="14" fill="{MUTED}">{html.escape(self.subtitle)}</text>')
        for t in nice_ticks(y0, y1):
            yy = sy(t)
            o.append(f'<line x1="{L}" x2="{R}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{GRID}"/>')
            o.append(f'<text x="{L - 8}" y="{yy + 5:.1f}" font-size="14" text-anchor="end" fill="{MUTED}">{fmt_tick(t)}</text>')
        if self.xcats is not None:
            for i, lab in enumerate(self.xcats):
                o.append(f'<text x="{sx(i):.1f}" y="{B + 22}" font-size="14" text-anchor="middle" fill="{MUTED}">{html.escape(str(lab))}</text>')
        else:
            for t in nice_ticks(x0, x1):
                o.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="{B}" y2="{B + 5}" stroke="{MUTED}"/>')
                o.append(f'<text x="{sx(t):.1f}" y="{B + 22}" font-size="14" text-anchor="middle" fill="{MUTED}">{fmt_tick(t)}</text>')
        o.append(f'<line x1="{L}" x2="{R}" y1="{B}" y2="{B}" stroke="{INK}"/>')
        o.append(f'<line x1="{L}" x2="{L}" y1="{T}" y2="{B}" stroke="{INK}"/>')
        o.append(f'<text x="{(L + R) / 2}" y="{self.h - 30}" font-size="16" text-anchor="middle" fill="{INK}">{html.escape(self.xlabel)}</text>')
        o.append(f'<text transform="translate(24,{(T + B) / 2}) rotate(-90)" font-size="16" text-anchor="middle" fill="{INK}">{html.escape(self.ylabel)}</text>')
        o.append(f'<clipPath id="plot"><rect x="{L}" y="{T}" width="{R - L}" height="{B - T}"/></clipPath><g clip-path="url(#plot)">')
        for it in self.items:
            c = it["color"]
            if it["kind"] == "hline":
                o.append(f'<line x1="{L}" x2="{R}" y1="{sy(it["y"]):.1f}" y2="{sy(it["y"]):.1f}" stroke="{c}" stroke-width="1.6" stroke-dasharray="{it["dash"]}"/>')
                if it["label"]:
                    lx, anchor = (R - 6, "end") if it.get("side", "right") == "right" else (L + 6, "start")
                    o.append(f'<text x="{lx}" y="{sy(it["y"]) - 6:.1f}" font-size="13" text-anchor="{anchor}" fill="{c}">{html.escape(it["label"])}</text>')
            elif it["kind"] == "line":
                pts = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(it["x"], it["y"]) if b is not None and math.isfinite(b))
                dash = f' stroke-dasharray="{it["dash"]}"' if it["dash"] else ""
                o.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="{it["width"]}"{dash}/>')
                if it["marker"]:
                    o += [f'<circle cx="{sx(a):.1f}" cy="{sy(b):.1f}" r="4" fill="{c}"/>' for a, b in zip(it["x"], it["y"]) if math.isfinite(b)]
            elif it["kind"] == "scatter":
                o += [f'<circle cx="{sx(a):.1f}" cy="{sy(b):.1f}" r="{it["r"]}" fill="{c}" fill-opacity="{it["opacity"]}"/>'
                      for a, b in zip(it["x"], it["y"]) if math.isfinite(b)]
            elif it["kind"] == "err":
                for a, b, lo, hi in zip(it["x"], it["y"], it["lo"], it["hi"]):
                    o.append(f'<line x1="{sx(a):.1f}" x2="{sx(a):.1f}" y1="{sy(lo):.1f}" y2="{sy(hi):.1f}" stroke="{c}" stroke-width="2"/>')
                    for v in (lo, hi):
                        o.append(f'<line x1="{sx(a) - 6:.1f}" x2="{sx(a) + 6:.1f}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{c}" stroke-width="2"/>')
                    o.append(f'<circle cx="{sx(a):.1f}" cy="{sy(b):.1f}" r="5" fill="{c}"/>')
            elif it["kind"] == "box":
                half = (sx(it["bw"]) - sx(0)) / 2
                for a, s in zip(it["x"], it["stats"]):
                    xc = sx(a)
                    o.append(f'<line x1="{xc:.1f}" x2="{xc:.1f}" y1="{sy(s["p5"]):.1f}" y2="{sy(s["p95"]):.1f}" stroke="{c}" stroke-width="1.5"/>')
                    o.append(f'<rect x="{xc - half:.1f}" y="{sy(s["q3"]):.1f}" width="{2 * half:.1f}" height="{sy(s["q1"]) - sy(s["q3"]):.1f}" fill="{c}" fill-opacity="0.18" stroke="{c}" stroke-width="1.8"/>')
                    o.append(f'<line x1="{xc - half:.1f}" x2="{xc + half:.1f}" y1="{sy(s["med"]):.1f}" y2="{sy(s["med"]):.1f}" stroke="{c}" stroke-width="3"/>')
        o.append("</g>")
        labelled = [it for it in self.items if it.get("label") and it["kind"] != "hline"]
        for i, it in enumerate(labelled):
            yy = T + 14 + i * 22
            o.append(f'<rect x="{L + 14}" y="{yy - 10}" width="14" height="14" fill="{it["color"]}"/>')
            o.append(f'<text x="{L + 34}" y="{yy + 2}" font-size="14" fill="{INK}">{html.escape(it["label"])}</text>')
        o.append("</svg>")
        return "\n".join(o)

    def save(self, png_path):
        svg_path = os.path.splitext(png_path)[0] + ".svg"
        with open(svg_path, "w") as fh:
            fh.write(self.svg())
        subprocess.run(["rsvg-convert", "-o", png_path, svg_path], check=True)
        os.remove(svg_path)
        return png_path


def box_stats(values):
    import numpy as np
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    p5, q1, med, q3, p95 = np.percentile(v, [5, 25, 50, 75, 95])
    return {"p5": p5, "q1": q1, "med": med, "q3": q3, "p95": p95}
