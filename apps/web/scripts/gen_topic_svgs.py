#!/usr/bin/env python3
"""
Generate decorative, topic-themed SVG assets for the ScrollWise feed.

For each topic we emit 30 SVGs (10 small / 10 medium / 10 large), every one
seeded deterministically so re-running this script reproduces the exact same
files (no churn in git). Alongside the SVGs we write a `manifest.json` carrying
metadata for every asset — the API / template selector can use it to pick an
on-theme background for a post.

  Output: apps/web/public/topic-svgs/
    <topic>/<size>/<topic>-<size>-NN.svg   (180 files)
    manifest.json                           (metadata for all 180)

No third-party dependencies — stdlib only. Run with any Python 3.8+.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

# --- Topic catalog (mirrors the request) ------------------------------------

TOPICS = [
    {"topic": "physics",   "mood": "wave patterns, energy fields, particles",
     "motifs": ["waves", "field", "particles"]},
    {"topic": "chemistry", "mood": "molecular bonds, bubbles, organic shapes",
     "motifs": ["molecule", "bubbles", "blob"]},
    {"topic": "cs",        "mood": "circuit grids, data flow, binary patterns",
     "motifs": ["circuit", "dataflow", "binary"]},
    {"topic": "math",      "mood": "geometric forms, fractals, graph grids",
     "motifs": ["geometry", "fractal", "graph"]},
    {"topic": "history",   "mood": "aged textures, timelines, map contours",
     "motifs": ["texture", "timeline", "contour"]},
    {"topic": "biology",   "mood": "organic curves, cell patterns, growth",
     "motifs": ["cells", "growth", "curves"]},
]

# Per-topic palette: a dark-ish background plus two accents that suit the mood.
PALETTES = {
    "physics":   {"bg": "#0b1026", "accent": "#5b8cff", "accent2": "#9b6bff", "accent3": "#39d0d8"},
    "chemistry": {"bg": "#08160f", "accent": "#2dd4a7", "accent2": "#f06aa6", "accent3": "#7be0c4"},
    "cs":        {"bg": "#06120b", "accent": "#3ddc84", "accent2": "#16c2c2", "accent3": "#a6f4c5"},
    "math":      {"bg": "#0e0a1f", "accent": "#8b7bff", "accent2": "#5b8cff", "accent3": "#c4b5fd"},
    "history":   {"bg": "#1b1305", "accent": "#caa15a", "accent2": "#b5651d", "accent3": "#e7cfa0"},
    "biology":   {"bg": "#071508", "accent": "#56c26a", "accent2": "#a3d977", "accent3": "#2f9e6b"},
}

# Size profiles: dimensions + a density multiplier that scales element counts.
SIZES = {
    "small":  {"w": 160, "h": 160, "density": 0.6, "count": 10},
    "medium": {"w": 400, "h": 300, "density": 1.0, "count": 10},
    "large":  {"w": 960, "h": 540, "density": 1.8, "count": 10},
}


# --- Deterministic RNG (LCG) -------------------------------------------------

def _hash(s: str) -> int:
    """FNV-1a 32-bit hash — same idea as the web Deco component's seed."""
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


@dataclass
class Rng:
    state: int

    def next(self) -> float:
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state / 0x100000000

    def rng(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.next()

    def irange(self, lo: int, hi: int) -> int:
        return int(self.rng(lo, hi + 1))

    def pick(self, seq):
        return seq[self.irange(0, len(seq) - 1)]


def f(x: float) -> str:
    """Trim floats so the markup stays compact (and diff-stable)."""
    return f"{x:.2f}".rstrip("0").rstrip(".")


# --- Motif primitives --------------------------------------------------------
# Each returns a list of SVG element strings drawn into a w*h canvas.

def m_waves(r: Rng, w, h, p, d):
    out = []
    rows = max(2, int(5 * d))
    for i in range(rows):
        y = h * (i + 1) / (rows + 1) + r.rng(-8, 8)
        amp = r.rng(6, 22) * d
        wl = r.rng(40, 90)
        phase = r.rng(0, math.tau)
        pts = []
        steps = max(8, int(w / 12))
        for s in range(steps + 1):
            x = w * s / steps
            yy = y + amp * math.sin(phase + x / wl)
            pts.append(f"{f(x)},{f(yy)}")
        col = r.pick([p["accent"], p["accent3"]])
        out.append(f'<polyline points="{" ".join(pts)}" fill="none" '
                   f'stroke="{col}" stroke-width="{f(r.rng(1, 2.2))}" '
                   f'opacity="{f(r.rng(0.15, 0.4))}"/>')
    return out


def m_field(r: Rng, w, h, p, d):
    out = []
    cx, cy = r.rng(w * 0.3, w * 0.7), r.rng(h * 0.3, h * 0.7)
    rings = max(3, int(6 * d))
    for i in range(rings):
        rad = (i + 1) * min(w, h) / (rings * 1.6)
        out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(rad)}" fill="none" '
                   f'stroke="{p["accent2"]}" stroke-width="1" '
                   f'opacity="{f(0.28 - i * 0.03)}"/>')
    # radial field lines
    spokes = max(6, int(10 * d))
    for i in range(spokes):
        a = i / spokes * math.tau + r.rng(0, 0.3)
        rr = min(w, h) * 0.45
        out.append(f'<line x1="{f(cx)}" y1="{f(cy)}" x2="{f(cx + math.cos(a) * rr)}" '
                   f'y2="{f(cy + math.sin(a) * rr)}" stroke="{p["accent"]}" '
                   f'stroke-width="0.6" opacity="0.12"/>')
    return out


def m_particles(r: Rng, w, h, p, d):
    out = []
    n = max(6, int(20 * d))
    for _ in range(n):
        x, y = r.rng(0, w), r.rng(0, h)
        rad = r.rng(1, 4) * d
        col = r.pick([p["accent"], p["accent2"], p["accent3"]])
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rad)}" fill="{col}" '
                   f'opacity="{f(r.rng(0.2, 0.55))}"/>')
        if r.next() > 0.6:  # motion trail
            tx, ty = x - r.rng(8, 24), y - r.rng(-6, 6)
            out.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(tx)}" y2="{f(ty)}" '
                       f'stroke="{col}" stroke-width="0.8" opacity="0.18"/>')
    return out


def m_molecule(r: Rng, w, h, p, d):
    out = []
    nodes = []
    n = max(4, int(8 * d))
    for _ in range(n):
        nodes.append((r.rng(w * 0.1, w * 0.9), r.rng(h * 0.1, h * 0.9)))
    # bonds: connect each node to its nearest couple of neighbours
    for i, (x1, y1) in enumerate(nodes):
        dists = sorted(range(len(nodes)),
                       key=lambda j: (nodes[j][0] - x1) ** 2 + (nodes[j][1] - y1) ** 2)
        for j in dists[1:3]:
            x2, y2 = nodes[j]
            out.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" '
                       f'stroke="{p["accent3"]}" stroke-width="1.4" opacity="0.3"/>')
    for (x, y) in nodes:
        rad = r.rng(4, 9) * (0.7 + d * 0.3)
        col = r.pick([p["accent"], p["accent2"]])
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rad)}" fill="{col}" '
                   f'opacity="0.5"/>')
    return out


def m_bubbles(r: Rng, w, h, p, d):
    out = []
    n = max(5, int(14 * d))
    for _ in range(n):
        x, y = r.rng(0, w), r.rng(0, h)
        rad = r.rng(4, 26) * d
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(rad)}" fill="none" '
                   f'stroke="{p["accent"]}" stroke-width="1" opacity="0.22"/>')
        out.append(f'<circle cx="{f(x - rad * 0.3)}" cy="{f(y - rad * 0.3)}" '
                   f'r="{f(rad * 0.18)}" fill="{p["accent3"]}" opacity="0.4"/>')
    return out


def m_blob(r: Rng, w, h, p, d):
    out = []
    blobs = max(1, int(2 * d))
    for _ in range(blobs):
        cx, cy = r.rng(w * 0.2, w * 0.8), r.rng(h * 0.2, h * 0.8)
        pts = []
        lobes = r.irange(5, 8)
        base = r.rng(20, 50) * d
        for i in range(lobes):
            a = i / lobes * math.tau
            rad = base * r.rng(0.7, 1.3)
            pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
        dpath = _smooth_closed(pts)
        out.append(f'<path d="{dpath}" fill="{p["accent2"]}" opacity="0.12"/>')
        out.append(f'<path d="{dpath}" fill="none" stroke="{p["accent"]}" '
                   f'stroke-width="1" opacity="0.25"/>')
    return out


def m_circuit(r: Rng, w, h, p, d):
    out = []
    grid = max(20, int(min(w, h) / (3 + d)))
    # orthogonal traces
    traces = max(4, int(8 * d))
    for _ in range(traces):
        x = round(r.rng(0, w) / grid) * grid
        y = round(r.rng(0, h) / grid) * grid
        path = [f"M{f(x)},{f(y)}"]
        for _ in range(r.irange(2, 4)):
            if r.next() > 0.5:
                x += r.pick([-1, 1]) * grid * r.irange(1, 3)
            else:
                y += r.pick([-1, 1]) * grid * r.irange(1, 3)
            x = max(0, min(w, x)); y = max(0, min(h, y))
            path.append(f"L{f(x)},{f(y)}")
        out.append(f'<path d="{" ".join(path)}" fill="none" stroke="{p["accent"]}" '
                   f'stroke-width="1.2" opacity="0.3"/>')
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="2.6" fill="{p["accent3"]}" opacity="0.55"/>')
    return out


def m_dataflow(r: Rng, w, h, p, d):
    out = []
    lanes = max(2, int(4 * d))
    for i in range(lanes):
        y = h * (i + 1) / (lanes + 1)
        out.append(f'<line x1="0" y1="{f(y)}" x2="{f(w)}" y2="{f(y)}" '
                   f'stroke="{p["accent3"]}" stroke-width="0.8" '
                   f'stroke-dasharray="2 8" opacity="0.25"/>')
        for _ in range(r.irange(2, 4)):
            x = r.rng(0, w - 18)
            out.append(f'<path d="M{f(x)},{f(y - 4)} L{f(x + 10)},{f(y)} L{f(x)},{f(y + 4)} Z" '
                       f'fill="{p["accent"]}" opacity="0.5"/>')
    return out


def m_binary(r: Rng, w, h, p, d):
    out = []
    # Cell scales with the canvas (≈16 columns) so the glyph count stays bounded
    # regardless of size — keeps even the large assets a few KB, not hundreds.
    cell = max(16, int(w / 16))
    cols = int(w / cell); rows = int(h / cell)
    for cx in range(cols):
        for cy in range(rows):
            if r.next() > 0.55:
                continue
            x = cx * cell + cell * 0.3
            y = cy * cell + cell * 0.7
            ch = "1" if r.next() > 0.5 else "0"
            out.append(f'<text x="{f(x)}" y="{f(y)}" font-family="monospace" '
                       f'font-size="{f(cell * 0.6)}" fill="{p["accent"]}" '
                       f'opacity="{f(r.rng(0.12, 0.4))}">{ch}</text>')
    return out


def m_geometry(r: Rng, w, h, p, d):
    out = []
    n = max(3, int(6 * d))
    for _ in range(n):
        cx, cy = r.rng(w * 0.15, w * 0.85), r.rng(h * 0.15, h * 0.85)
        sides = r.irange(3, 6)
        rad = r.rng(12, 40) * d
        rot = r.rng(0, math.tau)
        pts = [f"{f(cx + math.cos(rot + k / sides * math.tau) * rad)},"
               f"{f(cy + math.sin(rot + k / sides * math.tau) * rad)}" for k in range(sides)]
        col = r.pick([p["accent"], p["accent2"], p["accent3"]])
        out.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{col}" '
                   f'stroke-width="1.2" opacity="{f(r.rng(0.2, 0.45))}"/>')
    return out


def m_fractal(r: Rng, w, h, p, d):
    out = []
    depth = 3 + int(d)

    def tri(x, y, size, dep):
        if dep == 0 or size < 6:
            return
        half = size / 2
        out.append(f'<polygon points="{f(x)},{f(y)} {f(x - half)},{f(y + size)} '
                   f'{f(x + half)},{f(y + size)}" fill="none" stroke="{p["accent2"]}" '
                   f'stroke-width="0.8" opacity="{f(0.15 + dep * 0.06)}"/>')
        tri(x, y, half, dep - 1)
        tri(x - half / 2, y + half, half, dep - 1)
        tri(x + half / 2, y + half, half, dep - 1)

    tri(w / 2, h * 0.12, min(w, h) * 0.6, depth)
    return out


def m_graph(r: Rng, w, h, p, d):
    out = []
    # axes + grid
    step = max(20, int(min(w, h) / (5 + d)))
    for x in range(0, int(w), step):
        out.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{f(h)}" stroke="{p["accent3"]}" '
                   f'stroke-width="0.5" opacity="0.1"/>')
    for y in range(0, int(h), step):
        out.append(f'<line x1="0" y1="{y}" x2="{f(w)}" y2="{y}" stroke="{p["accent3"]}" '
                   f'stroke-width="0.5" opacity="0.1"/>')
    # a plotted curve
    kind = r.pick(["sin", "parab", "exp"])
    pts = []
    steps = max(10, int(w / 10))
    for s in range(steps + 1):
        t = s / steps
        x = t * w
        if kind == "sin":
            y = h * (0.5 - 0.35 * math.sin(t * math.tau * r.rng(1, 2)))
        elif kind == "parab":
            y = h * (0.9 - 0.8 * (2 * t - 1) ** 2)
        else:
            y = h * (0.95 - 0.85 * (math.exp(t * 2) - 1) / (math.exp(2) - 1))
        pts.append(f"{f(x)},{f(y)}")
    out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{p["accent"]}" '
               f'stroke-width="2" opacity="0.55"/>')
    return out


def m_texture(r: Rng, w, h, p, d):
    out = []
    n = max(30, int(120 * d))
    for _ in range(n):
        x, y = r.rng(0, w), r.rng(0, h)
        ln = r.rng(1, 4)
        a = r.rng(0, math.tau)
        out.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + math.cos(a) * ln)}" '
                   f'y2="{f(y + math.sin(a) * ln)}" stroke="{p["accent3"]}" '
                   f'stroke-width="0.6" opacity="{f(r.rng(0.04, 0.16))}"/>')
    return out


def m_timeline(r: Rng, w, h, p, d):
    out = []
    y = h * 0.5
    out.append(f'<line x1="{f(w * 0.05)}" y1="{f(y)}" x2="{f(w * 0.95)}" y2="{f(y)}" '
               f'stroke="{p["accent"]}" stroke-width="1.6" opacity="0.4"/>')
    n = max(3, int(6 * d))
    for i in range(n):
        x = w * (0.05 + 0.9 * i / max(1, n - 1))
        out.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="4" fill="{p["accent2"]}" opacity="0.6"/>')
        th = r.rng(10, 28) * (1 if i % 2 else -1)
        out.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x)}" y2="{f(y + th)}" '
                   f'stroke="{p["accent3"]}" stroke-width="1" opacity="0.3"/>')
    return out


def m_contour(r: Rng, w, h, p, d):
    out = []
    cx, cy = r.rng(w * 0.3, w * 0.7), r.rng(h * 0.3, h * 0.7)
    rings = max(3, int(6 * d))
    for i in range(rings):
        base = (i + 1) * min(w, h) / (rings * 1.8)
        lobes = r.irange(7, 11)
        pts = [(cx + math.cos(k / lobes * math.tau) * base * r.rng(0.82, 1.18),
                cy + math.sin(k / lobes * math.tau) * base * r.rng(0.82, 1.18))
               for k in range(lobes)]
        out.append(f'<path d="{_smooth_closed(pts)}" fill="none" stroke="{p["accent"]}" '
                   f'stroke-width="0.9" opacity="{f(0.3 - i * 0.03)}"/>')
    return out


def m_cells(r: Rng, w, h, p, d):
    out = []
    n = max(5, int(12 * d))
    for _ in range(n):
        cx, cy = r.rng(w * 0.1, w * 0.9), r.rng(h * 0.1, h * 0.9)
        rad = r.rng(10, 30) * (0.7 + d * 0.3)
        lobes = r.irange(6, 9)
        pts = [(cx + math.cos(k / lobes * math.tau) * rad * r.rng(0.85, 1.15),
                cy + math.sin(k / lobes * math.tau) * rad * r.rng(0.85, 1.15))
               for k in range(lobes)]
        out.append(f'<path d="{_smooth_closed(pts)}" fill="{p["accent2"]}" opacity="0.1"/>')
        out.append(f'<path d="{_smooth_closed(pts)}" fill="none" stroke="{p["accent"]}" '
                   f'stroke-width="1" opacity="0.3"/>')
        out.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(rad * 0.28)}" '
                   f'fill="{p["accent3"]}" opacity="0.4"/>')
    return out


def m_growth(r: Rng, w, h, p, d):
    out = []

    def branch(x, y, ang, length, dep):
        if dep == 0 or length < 6:
            return
        x2 = x + math.cos(ang) * length
        y2 = y + math.sin(ang) * length
        out.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x2)}" y2="{f(y2)}" '
                   f'stroke="{p["accent"]}" stroke-width="{f(dep * 0.5)}" '
                   f'opacity="{f(0.15 + dep * 0.06)}"/>')
        if dep <= 2 and r.next() > 0.4:
            out.append(f'<circle cx="{f(x2)}" cy="{f(y2)}" r="{f(r.rng(1.5, 3.5))}" '
                       f'fill="{p["accent3"]}" opacity="0.5"/>')
        branch(x2, y2, ang - r.rng(0.3, 0.7), length * 0.72, dep - 1)
        branch(x2, y2, ang + r.rng(0.3, 0.7), length * 0.72, dep - 1)

    stems = max(1, int(2 * d))
    for _ in range(stems):
        branch(r.rng(w * 0.2, w * 0.8), h, -math.pi / 2 + r.rng(-0.3, 0.3),
               min(w, h) * 0.22, 4 + int(d))
    return out


def m_curves(r: Rng, w, h, p, d):
    out = []
    n = max(3, int(6 * d))
    for _ in range(n):
        x1, y1 = r.rng(0, w * 0.3), r.rng(0, h)
        x2, y2 = r.rng(w * 0.7, w), r.rng(0, h)
        cx1, cy1 = r.rng(0, w), r.rng(0, h)
        cx2, cy2 = r.rng(0, w), r.rng(0, h)
        col = r.pick([p["accent"], p["accent3"]])
        out.append(f'<path d="M{f(x1)},{f(y1)} C{f(cx1)},{f(cy1)} {f(cx2)},{f(cy2)} '
                   f'{f(x2)},{f(y2)}" fill="none" stroke="{col}" '
                   f'stroke-width="{f(r.rng(1, 2.4))}" opacity="{f(r.rng(0.15, 0.4))}"/>')
    return out


MOTIFS = {
    "waves": m_waves, "field": m_field, "particles": m_particles,
    "molecule": m_molecule, "bubbles": m_bubbles, "blob": m_blob,
    "circuit": m_circuit, "dataflow": m_dataflow, "binary": m_binary,
    "geometry": m_geometry, "fractal": m_fractal, "graph": m_graph,
    "texture": m_texture, "timeline": m_timeline, "contour": m_contour,
    "cells": m_cells, "growth": m_growth, "curves": m_curves,
}


def _smooth_closed(pts):
    """Catmull-Rom-ish closed path through points → cubic bezier `d` string."""
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1x = p1[0] + (p2[0] - p0[0]) / 6
        c1y = p1[1] + (p2[1] - p0[1]) / 6
        c2x = p2[0] - (p3[0] - p1[0]) / 6
        c2y = p2[1] - (p3[1] - p1[1]) / 6
        d.append(f"C{f(c1x)},{f(c1y)} {f(c2x)},{f(c2y)} {f(p2[0])},{f(p2[1])}")
    d.append("Z")
    return " ".join(d)


# --- Asset assembly ----------------------------------------------------------

def build_svg(topic, mood, size, idx, motifs, palette):
    w, h, dens = SIZES[size]["w"], SIZES[size]["h"], SIZES[size]["density"]
    aid = f"{topic}-{size}-{idx:02d}"
    r = Rng(_hash(aid) ^ 0x9E3779B9)

    # Pick 2 motifs for this asset from the topic's pool, varying by index so
    # the 10 assets per size aren't all the same combination.
    pool = list(motifs)
    primary = pool[idx % len(pool)]
    secondary = pool[(idx + 1 + (idx // len(pool))) % len(pool)]
    chosen = [primary] if primary == secondary else [primary, secondary]

    grad = f"grad-{aid}"
    layers = []
    for name in chosen:
        layers.extend(MOTIFS[name](r, w, h, palette, dens))

    body = "\n  ".join(layers)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{topic} decorative background">\n'
        f'  <defs>\n'
        f'    <radialGradient id="{grad}" cx="50%" cy="35%" r="80%">\n'
        f'      <stop offset="0%" stop-color="{palette["accent"]}" stop-opacity="0.10"/>\n'
        f'      <stop offset="100%" stop-color="{palette["bg"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'  </defs>\n'
        f'  <rect width="{w}" height="{h}" fill="{palette["bg"]}"/>\n'
        f'  <rect width="{w}" height="{h}" fill="url(#{grad})"/>\n'
        f'  {body}\n'
        f'</svg>\n'
    )

    meta = {
        "id": aid,
        "topic": topic,
        "mood": mood,
        "size": size,
        "width": w,
        "height": h,
        "viewBox": f"0 0 {w} {h}",
        "motifs": chosen,
        "palette": {k: palette[k] for k in ("bg", "accent", "accent2", "accent3")},
        "seed": r.state,
        "file": f"{topic}/{size}/{aid}.svg",
        "tags": [topic, size, *chosen],
    }
    return aid, svg, meta


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_root = os.path.normpath(os.path.join(here, "..", "public", "topic-svgs"))
    manifest = {"generated_by": "scripts/gen_topic_svgs.py", "assets": []}

    total = 0
    for t in TOPICS:
        topic, mood, motifs = t["topic"], t["mood"], t["motifs"]
        palette = PALETTES[topic]
        for size in SIZES:
            count = SIZES[size]["count"]
            d = os.path.join(out_root, topic, size)
            os.makedirs(d, exist_ok=True)
            for i in range(1, count + 1):
                aid, svg, meta = build_svg(topic, mood, size, i, motifs, palette)
                with open(os.path.join(d, f"{aid}.svg"), "w") as fh:
                    fh.write(svg)
                manifest["assets"].append(meta)
                total += 1

    manifest["count"] = total
    manifest["topics"] = [t["topic"] for t in TOPICS]
    manifest["sizes"] = {s: {"width": SIZES[s]["w"], "height": SIZES[s]["h"],
                             "count": SIZES[s]["count"]} for s in SIZES}
    with open(os.path.join(out_root, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"Wrote {total} SVGs + manifest.json to {out_root}")


if __name__ == "__main__":
    main()
