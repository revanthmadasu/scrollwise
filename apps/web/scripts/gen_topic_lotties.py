#!/usr/bin/env python3
"""
Generate decorative, topic-themed Lottie (Bodymovin) animations for ScrollWise.

For each topic we emit 30 Lotties (10 small / 10 medium / 10 large), every one
seeded deterministically so re-running reproduces identical files. Each scene
loops cleanly over 90 frames @ 30fps (3s): all motion is periodic and returns
to its frame-0 state, so the lottie-react `loop` has no visible seam.

  Output: apps/web/public/topic-lotties/
    <topic>/<size>/<topic>-<size>-NN.json   (180 files, Bodymovin v5.7.4)
    manifest.json                            (metadata for all 180)

Schema mirrors src/templates/assets/compoundingLottie.ts so the same
lottie-react player renders these. Stdlib only; run with any Python 3.8+.
"""

from __future__ import annotations

import json
import math
import os

FR = 30
OP = 90  # loop length in frames (3s)

# --- Topic catalog (shared with the SVG generator) --------------------------

TOPICS = [
    {"topic": "physics",   "mood": "wave patterns, energy fields, particles",
     "elements": ["orbit", "pulse", "wave"]},
    {"topic": "chemistry", "mood": "molecular bonds, bubbles, organic shapes",
     "elements": ["molecule", "bubbles"]},
    {"topic": "cs",        "mood": "circuit grids, data flow, binary patterns",
     "elements": ["binary", "dataflow"]},
    {"topic": "math",      "mood": "geometric forms, fractals, graph grids",
     "elements": ["spin", "pulse", "orbit"]},
    {"topic": "history",   "mood": "aged textures, timelines, map contours",
     "elements": ["rings", "timeline"]},
    {"topic": "biology",   "mood": "organic curves, cell patterns, growth",
     "elements": ["cells", "growth"]},
]

PALETTES = {
    "physics":   {"bg": "#0b1026", "accent": "#5b8cff", "accent2": "#9b6bff", "accent3": "#39d0d8"},
    "chemistry": {"bg": "#08160f", "accent": "#2dd4a7", "accent2": "#f06aa6", "accent3": "#7be0c4"},
    "cs":        {"bg": "#06120b", "accent": "#3ddc84", "accent2": "#16c2c2", "accent3": "#a6f4c5"},
    "math":      {"bg": "#0e0a1f", "accent": "#8b7bff", "accent2": "#5b8cff", "accent3": "#c4b5fd"},
    "history":   {"bg": "#1b1305", "accent": "#caa15a", "accent2": "#b5651d", "accent3": "#e7cfa0"},
    "biology":   {"bg": "#071508", "accent": "#56c26a", "accent2": "#a3d977", "accent3": "#2f9e6b"},
}

SIZES = {
    "small":  {"w": 200, "h": 200, "density": 0.6, "count": 10},
    "medium": {"w": 400, "h": 300, "density": 1.0, "count": 10},
    "large":  {"w": 800, "h": 450, "density": 1.7, "count": 10},
}


# --- Deterministic RNG -------------------------------------------------------

def _hash(s: str) -> int:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class Rng:
    def __init__(self, seed: int):
        self.s = seed & 0xFFFFFFFF or 0x9E3779B9

    def next(self) -> float:
        self.s = (self.s * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.s / 0x100000000

    def f(self, lo, hi):
        return lo + (hi - lo) * self.next()

    def i(self, lo, hi):
        return int(self.f(lo, hi + 1))

    def pick(self, seq):
        return seq[self.i(0, len(seq) - 1)]


def rnd(x):
    """Round to 2dp and collapse -0.0, keeping JSON compact and stable."""
    v = round(x, 2)
    return 0.0 if v == 0 else v


def col(hex_str):
    h = hex_str.lstrip("#")
    return [rnd(int(h[0:2], 16) / 255), rnd(int(h[2:4], 16) / 255),
            rnd(int(h[4:6], 16) / 255), 1]


# --- Bodymovin builders ------------------------------------------------------

def stat(k):
    return {"a": 0, "k": k}


def _handles(dims, linear):
    """lottie-web needs the easing handle arrays to match the value's
    dimensionality (see compoundingLottie.ts). A length-1 handle on a 2-/3-D
    scale or position makes the layer fail to build and render nothing."""
    if linear:
        ix = iy = ox = oy = 0.5
    else:
        ix, iy, ox, oy = 0.6, 1, 0.4, 0
    return ({"x": [ix] * dims, "y": [iy] * dims},
            {"x": [ox] * dims, "y": [oy] * dims})


def anim(pairs, linear=False):
    """pairs: list of (t, value_list). Builds keyframes; loops cleanly if the
    caller makes the last value equal the first."""
    dims = len(pairs[0][1])
    i_h, o_h = _handles(dims, linear)
    ks = []
    for idx, (t, s) in enumerate(pairs):
        if idx == len(pairs) - 1:
            ks.append({"t": t, "s": s})
        else:
            ks.append({"t": t, "s": s, "i": i_h, "o": o_h})
    return {"a": 1, "k": ks}


def transform(o=100, r=0, p=(0, 0, 0), a=(0, 0, 0), s=(100, 100, 100)):
    def wrap(v):
        # An already-animated property arrives as a dict — pass it through.
        # Static vectors arrive as tuples/lists — wrap as a non-animated value.
        # (Must check dict BEFORE coercing to list, else list(dict) -> its keys.)
        if isinstance(v, dict):
            return v
        return stat(list(v) if isinstance(v, (list, tuple)) else v)
    return {"o": wrap(o), "r": wrap(r), "p": wrap(p), "a": wrap(a), "s": wrap(s)}


def shape_tr():
    return {"ty": "tr", "p": stat([0, 0]), "a": stat([0, 0]),
            "s": stat([100, 100]), "r": stat(0), "o": stat(100)}


def group(items, name="g"):
    return {"ty": "gr", "it": items + [shape_tr()], "nm": name}


def ellipse(w, h, p=(0, 0)):
    return {"ty": "el", "d": 1, "s": stat([w, h]), "p": stat(list(p)), "nm": "el"}


def rect(w, h, p=(0, 0), r=0):
    return {"ty": "rc", "d": 1, "s": stat([w, h]), "p": stat(list(p)),
            "r": stat(r), "nm": "rc"}


def poly(sides, radius, p=(0, 0)):
    return {"ty": "sr", "sy": 2, "d": 1, "pt": stat(sides), "p": stat(list(p)),
            "r": stat(0), "or": stat(radius), "os": stat(0), "nm": "sr"}


def fill(color, opacity=100):
    return {"ty": "fl", "c": stat(color), "o": stat(opacity), "r": 1, "nm": "fl"}


def stroke(color, opacity=100, width=2):
    return {"ty": "st", "c": stat(color), "o": stat(opacity), "w": stat(width),
            "lc": 2, "lj": 2, "nm": "st"}


_IND = [0]


def layer(name, shapes, ks):
    _IND[0] += 1
    return {"ddd": 0, "ind": _IND[0], "ty": 4, "nm": name, "sr": 1, "ks": ks,
            "ao": 0, "shapes": shapes, "ip": 0, "op": OP, "st": 0, "bm": 0}


# --- Animated element builders (each returns one or more layers) -------------

def el_pulse(r, w, h, p, n):
    """Concentric rings that breathe — energy field."""
    out = []
    cx, cy = r.f(w * 0.35, w * 0.65), r.f(h * 0.35, h * 0.65)
    color = col(r.pick([p["accent2"], p["accent"]]))
    rings = max(2, int(3 * n))
    for k in range(rings):
        rad = (k + 1) * min(w, h) / (rings * 2.2)
        phase = k * OP / (rings * 2)
        # breathing scale 90 -> 115 -> 90, phase-shifted per ring
        def at(t):
            return rnd(100 + 18 * math.sin(2 * math.pi * (t + phase) / OP))
        s = anim([(0, [at(0), at(0), 100]), (OP // 2, [at(OP / 2), at(OP / 2), 100]),
                  (OP, [at(OP), at(OP), 100])])
        o = anim([(0, [r.f(20, 40)]), (OP // 2, [r.f(40, 65)]), (OP, [r.f(20, 40)])])
        ks = transform(o=o, p=(cx, cy, 0), a=(cx, cy, 0), s=s)
        out.append(layer(f"ring{k}", [group([ellipse(rad * 2, rad * 2),
                   stroke(color, 100, r.f(1.5, 3))])], ks))
    return out


def el_orbit(r, w, h, p, n):
    """Particles orbiting a nucleus — energy/atomic feel."""
    out = []
    cx, cy = r.f(w * 0.35, w * 0.65), r.f(h * 0.35, h * 0.65)
    # nucleus
    out.append(layer("nucleus", [group([ellipse(10, 10), fill(col(p["accent"]), 100)])],
                     transform(o=70, p=(cx, cy, 0))))
    count = max(2, int(3 * n))
    for k in range(count):
        radius = r.f(min(w, h) * 0.12, min(w, h) * 0.4)
        start = r.f(0, 360)
        d = r.pick([1, -1])  # direction
        rr = anim([(0, [start]), (OP, [start + 360 * d])], linear=True)
        dotc = col(r.pick([p["accent3"], p["accent2"]]))
        dot = group([ellipse(r.f(5, 9), r.f(5, 9), (radius, 0)), fill(dotc, 100)])
        ks = transform(o=r.f(55, 85), r=rr, p=(cx, cy, 0), a=(0, 0, 0))
        out.append(layer(f"orbit{k}", [dot], ks))
    return out


def el_wave(r, w, h, p, n):
    """Row(s) of dots oscillating vertically with a phase gradient → traveling wave."""
    out = []
    rows = max(1, int(2 * n))
    for row in range(rows):
        baseY = h * (row + 1) / (rows + 1) + r.f(-10, 10)
        amp = r.f(10, 26)
        dots = max(5, int(9 * n))
        color = col(r.pick([p["accent"], p["accent3"]]))
        for di in range(dots):
            x = w * (di + 0.5) / dots
            phase = di / dots * OP * r.pick([1, 1, 2])
            def at(t):
                return rnd(baseY + amp * math.sin(2 * math.pi * (t + phase) / OP))
            samples = [(int(OP * j / 4), [rnd(x), at(OP * j / 4), 0]) for j in range(5)]
            ks = transform(o=r.f(40, 75), p=anim(samples))
            out.append(layer(f"wd{row}_{di}",
                       [group([ellipse(5, 5), fill(color, 100)])], ks))
    return out


def el_molecule(r, w, h, p, n):
    """Bonded nodes (static bonds) with nuclei that bob in scale."""
    out = []
    count = max(3, int(5 * n))
    nodes = [(r.f(w * 0.15, w * 0.85), r.f(h * 0.15, h * 0.85)) for _ in range(count)]
    # bonds: nearest-neighbour lines on a single static layer
    bonds = []
    for idx, (x1, y1) in enumerate(nodes):
        order = sorted(range(count), key=lambda j: (nodes[j][0] - x1) ** 2 + (nodes[j][1] - y1) ** 2)
        for j in order[1:3]:
            x2, y2 = nodes[j]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            length = math.hypot(x2 - x1, y2 - y1)
            ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
            bonds.append(layer("bond",
                [group([rect(length, 2, (0, 0)), fill(col(p["accent3"]), 100)])],
                transform(o=28, r=ang, p=(mx, my, 0))))
    out.extend(bonds)
    for k, (x, y) in enumerate(nodes):
        phase = k * OP / count
        def at(t):
            return rnd(100 + 22 * math.sin(2 * math.pi * (t + phase) / OP))
        s = anim([(0, [at(0)] * 2 + [100]), (OP // 2, [at(OP / 2)] * 2 + [100]),
                  (OP, [at(OP)] * 2 + [100])])
        rad = r.f(8, 16)
        out.append(layer(f"node{k}",
            [group([ellipse(rad, rad), fill(col(r.pick([p["accent"], p["accent2"]])), 100)])],
            transform(o=r.f(55, 80), p=(x, y, 0), a=(x, y, 0), s=s)))
    return out


def el_bubbles(r, w, h, p, n):
    """Bubbles rising and fading — clean loop via fade in/out."""
    out = []
    count = max(4, int(9 * n))
    for k in range(count):
        x = r.f(w * 0.08, w * 0.92)
        size = r.f(8, 26)
        t0 = r.i(0, OP)  # stagger start (wraps within the loop)
        rise = r.f(h * 0.5, h * 0.9)
        y0 = h + size
        # one rise across the loop, offset by t0 using two segments that wrap
        def y(frac):
            return rnd(y0 - rise * frac)
        pts = [(0, [x, y(0), 0]), (OP, [x, y(1), 0])]
        op_kf = anim([(0, [0]), (int(OP * 0.2), [r.f(30, 55)]),
                      (int(OP * 0.8), [r.f(30, 55)]), (OP, [0])])
        ks = transform(o=op_kf, p=anim(pts, linear=True))
        out.append(layer(f"bub{k}", [group([ellipse(size, size),
                   stroke(col(p["accent"]), 100, 1.5)])], ks))
    return out


def el_binary(r, w, h, p, n):
    """Grid of 0/1-ish dots blinking in opacity — binary pattern."""
    out = []
    cell = max(30, int(w / 11))
    cols = int(w / cell)
    rows = int(h / cell)
    color = col(p["accent"])
    for cxi in range(cols):
        for cyi in range(rows):
            if r.next() > 0.55:  # ~half the grid lit, bounded regardless of size
                continue
            x = cxi * cell + cell / 2
            y = cyi * cell + cell / 2
            phase = r.i(0, OP)
            lo, hi = r.f(8, 20), r.f(45, 80)
            op_kf = anim([(0, [lo]), (OP // 2, [hi]), (OP, [lo])])
            # rotate the phase by shifting via start time isn't trivial; vary lo/hi/size instead
            sz = r.pick([4, 5, 7])
            shape = poly(4, sz) if r.next() > 0.5 else ellipse(sz, sz)
            out.append(layer("bit", [group([shape, fill(color, 100)])],
                       transform(o=op_kf, p=(rnd(x), rnd(y), 0))))
    return out


def el_dataflow(r, w, h, p, n):
    """Packets sliding along horizontal lanes — data flow."""
    out = []
    lanes = max(2, int(3 * n))
    for li in range(lanes):
        y = h * (li + 1) / (lanes + 1)
        # static lane track
        out.append(layer("track", [group([rect(w * 0.9, 1.5, (0, 0), 0),
                   fill(col(p["accent3"]), 100)])], transform(o=18, p=(w / 2, y, 0))))
        packets = r.i(1, 2)
        for pk in range(packets):
            color = col(r.pick([p["accent"], p["accent2"]]))
            x0, x1 = w * 0.05, w * 0.95
            d = r.pick([1, -1])
            sx, ex = (x0, x1) if d == 1 else (x1, x0)
            pts = [(0, [sx, y, 0]), (OP, [ex, y, 0])]
            op_kf = anim([(0, [0]), (int(OP * 0.15), [r.f(60, 90)]),
                          (int(OP * 0.85), [r.f(60, 90)]), (OP, [0])])
            out.append(layer(f"pkt{li}_{pk}",
                [group([rect(r.f(10, 18), 4, (0, 0), 2), fill(color, 100)])],
                transform(o=op_kf, p=anim(pts, linear=True))))
    return out


def el_spin(r, w, h, p, n):
    """Rotating polygons — geometric forms."""
    out = []
    count = max(2, int(4 * n))
    for k in range(count):
        cx, cy = r.f(w * 0.15, w * 0.85), r.f(h * 0.15, h * 0.85)
        sides = r.i(3, 6)
        radius = r.f(14, 40)
        d = r.pick([1, -1])
        start = r.f(0, 360)
        rr = anim([(0, [start]), (OP, [start + 360 * d])], linear=True)
        color = col(r.pick([p["accent"], p["accent2"], p["accent3"]]))
        out.append(layer(f"poly{k}",
            [group([poly(sides, radius), stroke(color, 100, r.f(1.5, 2.5))])],
            transform(o=r.f(35, 65), r=rr, p=(cx, cy, 0), a=(0, 0, 0))))
    return out


def el_rings(r, w, h, p, n):
    """Slowly rotating, slightly elliptical contour rings — map/era feel."""
    out = []
    cx, cy = r.f(w * 0.3, w * 0.7), r.f(h * 0.3, h * 0.7)
    rings = max(2, int(4 * n))
    for k in range(rings):
        rad = (k + 1) * min(w, h) / (rings * 2.4)
        d = r.pick([1, -1])
        rr = anim([(0, [0]), (OP, [360 * d * r.f(0.3, 0.6)]), ], linear=True)
        # not a clean 360 multiple; make it return for clean loop:
        rr = anim([(0, [0]), (OP // 2, [r.f(8, 20) * d]), (OP, [0])])
        color = col(p["accent"])
        out.append(layer(f"contour{k}",
            [group([ellipse(rad * 2, rad * 1.7), stroke(color, 100, 1.5)])],
            transform(o=rnd(34 - k * 3), r=rr, p=(cx, cy, 0), a=(0, 0, 0))))
    return out


def el_timeline(r, w, h, p, n):
    """A baseline with markers that light up in sequence — timeline."""
    out = []
    y = h * 0.5
    out.append(layer("axis", [group([rect(w * 0.9, 2, (0, 0)), fill(col(p["accent"]), 100)])],
                     transform(o=40, p=(w / 2, y, 0))))
    marks = max(3, int(6 * n))
    for k in range(marks):
        x = w * (0.05 + 0.9 * k / max(1, marks - 1))
        # light-up window travels along the marks
        center = OP * k / marks
        lo, hi = 30, 95
        def at(t):
            dt = min(abs(t - center), OP - abs(t - center))
            return rnd(lo + (hi - lo) * max(0, 1 - dt / (OP / marks)))
        op_kf = anim([(int(OP * j / 6), [at(OP * j / 6)]) for j in range(7)])
        color = col(r.pick([p["accent2"], p["accent3"]]))
        out.append(layer(f"mark{k}", [group([ellipse(9, 9), fill(color, 100)])],
                   transform(o=op_kf, p=(rnd(x), y, 0))))
    return out


def el_cells(r, w, h, p, n):
    """Cells with nuclei, gently pulsing — cell patterns."""
    out = []
    count = max(3, int(6 * n))
    for k in range(count):
        cx, cy = r.f(w * 0.15, w * 0.85), r.f(h * 0.15, h * 0.85)
        rad = r.f(16, 40)
        phase = r.i(0, OP)
        def at(t):
            return rnd(100 + 12 * math.sin(2 * math.pi * (t + phase) / OP))
        s = anim([(0, [at(0)] * 2 + [100]), (OP // 2, [at(OP / 2)] * 2 + [100]),
                  (OP, [at(OP)] * 2 + [100])])
        membrane = group([ellipse(rad * 2, rad * 1.8), stroke(col(p["accent"]), 100, 1.5)])
        out.append(layer(f"cell{k}", [membrane],
                   transform(o=r.f(28, 50), p=(cx, cy, 0), a=(cx, cy, 0), s=s)))
        out.append(layer(f"nuc{k}",
            [group([ellipse(rad * 0.5, rad * 0.5), fill(col(p["accent3"]), 100)])],
            transform(o=r.f(40, 70), p=(cx, cy, 0), a=(cx, cy, 0), s=s)))
    return out


def el_growth(r, w, h, p, n):
    """Stems that scale up from the base (growing), then fade — clean loop."""
    out = []
    count = max(2, int(4 * n))
    for k in range(count):
        x = r.f(w * 0.15, w * 0.85)
        length = r.f(h * 0.25, h * 0.6)
        baseY = h
        tilt = r.f(-12, 12)
        grow_start = r.i(0, OP // 3)
        # scale Y 0 -> 100 (grow), hold, then fade out near loop end
        sy = anim([(grow_start, [100, 0, 100]),
                   (grow_start + OP // 3, [100, 100, 100]), (OP, [100, 100, 100])])
        op_kf = anim([(grow_start, [0]), (grow_start + 8, [r.f(40, 70)]),
                      (int(OP * 0.82), [r.f(40, 70)]), (OP, [0])])
        stem = group([rect(r.f(2.5, 5), length, (0, -length / 2), 2),
                      fill(col(r.pick([p["accent"], p["accent3"]])), 100)])
        ks = transform(o=op_kf, r=tilt, p=(x, baseY, 0), a=(x, baseY, 0), s=sy)
        # move the rect so its anchor sits at the base (anchor == layer pos)
        stem["it"][0]["p"] = stat([x, baseY - length / 2])
        # bud at the tip
        out.append(layer(f"stem{k}", [stem], ks))
    return out


ELEMENTS = {
    "pulse": el_pulse, "orbit": el_orbit, "wave": el_wave,
    "molecule": el_molecule, "bubbles": el_bubbles,
    "binary": el_binary, "dataflow": el_dataflow,
    "spin": el_spin, "rings": el_rings, "timeline": el_timeline,
    "cells": el_cells, "growth": el_growth,
}


def bg_layer(w, h, p):
    return layer("bg", [group([rect(w, h, (w / 2, h / 2)), fill(col(p["bg"]), 100)])],
                 transform(o=100, p=(0, 0, 0)))


# --- Assembly ----------------------------------------------------------------

def build_lottie(topic, mood, size, idx, elements, palette):
    w, h, n = SIZES[size]["w"], SIZES[size]["h"], SIZES[size]["density"]
    aid = f"{topic}-{size}-{idx:02d}"
    _IND[0] = 0
    r = Rng(_hash(aid) ^ 0x5BD1E995)

    pool = list(elements)
    primary = pool[idx % len(pool)]
    secondary = pool[(idx + 1 + idx // len(pool)) % len(pool)]
    chosen = [primary] if primary == secondary else [primary, secondary]

    layers = []
    for name in chosen:
        layers.extend(ELEMENTS[name](r, w, h, palette, n))
    layers.append(bg_layer(w, h, palette))  # last in array = painted behind

    data = {"v": "5.7.4", "fr": FR, "ip": 0, "op": OP, "w": w, "h": h,
            "nm": f"{topic} {size}", "ddd": 0, "assets": [], "layers": layers}

    meta = {
        "id": aid, "topic": topic, "mood": mood, "size": size,
        "width": w, "height": h, "fr": FR, "frames": OP,
        "duration_s": round(OP / FR, 2), "loop": True,
        "elements": chosen, "layer_count": len(layers),
        "palette": {k: palette[k] for k in ("bg", "accent", "accent2", "accent3")},
        "file": f"{topic}/{size}/{aid}.json",
        "tags": [topic, size, *chosen],
    }
    return aid, data, meta


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_root = os.path.normpath(os.path.join(here, "..", "public", "topic-lotties"))
    manifest = {"generated_by": "scripts/gen_topic_lotties.py", "schema": "bodymovin 5.7.4",
                "fr": FR, "frames": OP, "assets": []}

    total = 0
    for t in TOPICS:
        topic, mood, elements = t["topic"], t["mood"], t["elements"]
        palette = PALETTES[topic]
        for size in SIZES:
            d = os.path.join(out_root, topic, size)
            os.makedirs(d, exist_ok=True)
            for i in range(1, SIZES[size]["count"] + 1):
                aid, data, meta = build_lottie(topic, mood, size, i, elements, palette)
                with open(os.path.join(d, f"{aid}.json"), "w") as fh:
                    json.dump(data, fh, separators=(",", ":"))
                manifest["assets"].append(meta)
                total += 1

    manifest["count"] = total
    manifest["topics"] = [t["topic"] for t in TOPICS]
    manifest["sizes"] = {s: {"width": SIZES[s]["w"], "height": SIZES[s]["h"],
                             "count": SIZES[s]["count"]} for s in SIZES}
    with open(os.path.join(out_root, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"Wrote {total} Lottie JSONs + manifest.json to {out_root}")


if __name__ == "__main__":
    main()
