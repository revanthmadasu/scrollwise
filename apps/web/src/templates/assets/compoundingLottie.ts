/**
 * Hand-authored Lottie (Bodymovin schema) for the "Compounding" post.
 *
 * 400x220, 30fps, 3s loop. Six bars rise to exponentially increasing heights
 * (×1.5 each — the compounding curve), staggered, while a gold coin traces the
 * curve across their tops. Everything fades at the end so the loop restarts
 * cleanly (bars are zero-height/invisible at frame 0).
 *
 * Colors are baked amber (#fbbf24 bars, #fde68a coin) to match LottieHero's vibe.
 */

const BAR_COLOR = [0.984, 0.749, 0.141, 1]; // #fbbf24
const COIN_COLOR = [0.992, 0.902, 0.541, 1]; // #fde68a

const BASE_Y = 190;
const BAR_W = 30;
const OP = 90;
const GROW = 24; // frames a bar takes to grow

interface Bar {
  cx: number;
  h: number;
  g: number; // grow-start frame (stagger)
}

const BARS: Bar[] = [
  { cx: 70, h: 16, g: 0 },
  { cx: 122, h: 24, g: 8 },
  { cx: 174, h: 36, g: 16 },
  { cx: 226, h: 54, g: 24 },
  { cx: 278, h: 81, g: 32 },
  { cx: 330, h: 122, g: 40 },
];

function barLayer(b: Bar, ind: number) {
  return {
    ddd: 0,
    ind,
    ty: 4,
    nm: `bar${ind}`,
    sr: 1,
    ks: {
      // Fade out near the end so the loop reset (frame 90 -> 0) is invisible.
      o: {
        a: 1,
        k: [
          { t: 78, s: [100], i: { x: [0.4], y: [1] }, o: { x: [0.6], y: [0] } },
          { t: 88, s: [0] },
        ],
      },
      r: { a: 0, k: 0 },
      // Anchor == position == bottom-center, so Y-scaling grows the bar upward.
      p: { a: 0, k: [b.cx, BASE_Y, 0] },
      a: { a: 0, k: [b.cx, BASE_Y, 0] },
      s: {
        a: 1,
        k: [
          {
            t: b.g,
            s: [100, 0, 100],
            i: { x: [0.2, 0.2, 0.2], y: [1, 1, 1] },
            o: { x: [0.5, 0.5, 0.5], y: [0, 0, 0] },
          },
          { t: b.g + GROW, s: [100, 100, 100] },
        ],
      },
    },
    ao: 0,
    shapes: [
      {
        ty: "gr",
        it: [
          {
            ty: "rc",
            d: 1,
            s: { a: 0, k: [BAR_W, b.h] },
            p: { a: 0, k: [b.cx, BASE_Y - b.h / 2] },
            r: { a: 0, k: 5 },
            nm: "r",
          },
          { ty: "fl", c: { a: 0, k: BAR_COLOR }, o: { a: 0, k: 100 }, r: 1, nm: "f" },
          {
            ty: "tr",
            p: { a: 0, k: [0, 0] },
            a: { a: 0, k: [0, 0] },
            s: { a: 0, k: [100, 100] },
            r: { a: 0, k: 0 },
            o: { a: 0, k: 100 },
          },
        ],
        nm: "g",
      },
    ],
    ip: 0,
    op: OP,
    st: 0,
    bm: 0,
  };
}

// Coin rises along the bar tops (the exponential curve), fading in/out.
const coinLayer = {
  ddd: 0,
  ind: 10,
  ty: 4,
  nm: "coin",
  sr: 1,
  ks: {
    o: {
      a: 1,
      k: [
        { t: 10, s: [0], i: { x: [0.4], y: [1] }, o: { x: [0.6], y: [0] } },
        { t: 22, s: [100] },
        { t: 64, s: [100], i: { x: [0.4], y: [1] }, o: { x: [0.6], y: [0] } },
        { t: 74, s: [0] },
      ],
    },
    r: { a: 0, k: 0 },
    p: {
      a: 1,
      k: [
        { t: 12, s: [70, 162, 0], ti: [0, 0, 0], to: [0, 0, 0], i: { x: [0.33], y: [0.33] }, o: { x: [0.5], y: [0.5] } },
        { t: 24, s: [122, 154, 0], ti: [0, 0, 0], to: [0, 0, 0], i: { x: [0.33], y: [0.33] }, o: { x: [0.5], y: [0.5] } },
        { t: 36, s: [174, 142, 0], ti: [0, 0, 0], to: [0, 0, 0], i: { x: [0.33], y: [0.33] }, o: { x: [0.5], y: [0.5] } },
        { t: 48, s: [226, 124, 0], ti: [0, 0, 0], to: [0, 0, 0], i: { x: [0.33], y: [0.33] }, o: { x: [0.5], y: [0.5] } },
        { t: 58, s: [278, 97, 0], ti: [0, 0, 0], to: [0, 0, 0], i: { x: [0.33], y: [0.33] }, o: { x: [0.5], y: [0.5] } },
        { t: 64, s: [330, 56, 0] },
      ],
    },
    a: { a: 0, k: [0, 0, 0] },
    s: { a: 0, k: [100, 100, 100] },
  },
  ao: 0,
  shapes: [
    {
      ty: "gr",
      it: [
        { ty: "el", d: 1, s: { a: 0, k: [20, 20] }, p: { a: 0, k: [0, 0] }, nm: "e" },
        { ty: "fl", c: { a: 0, k: COIN_COLOR }, o: { a: 0, k: 100 }, r: 1, nm: "f" },
        {
          ty: "tr",
          p: { a: 0, k: [0, 0] },
          a: { a: 0, k: [0, 0] },
          s: { a: 0, k: [100, 100] },
          r: { a: 0, k: 0 },
          o: { a: 0, k: 100 },
        },
      ],
      nm: "g",
    },
  ],
  ip: 0,
  op: OP,
  st: 0,
  bm: 0,
};

// Static baseline the bars sit on.
const baselineLayer = {
  ddd: 0,
  ind: 99,
  ty: 4,
  nm: "baseline",
  sr: 1,
  ks: {
    o: { a: 0, k: 45 },
    r: { a: 0, k: 0 },
    p: { a: 0, k: [200, 192, 0] },
    a: { a: 0, k: [200, 192, 0] },
    s: { a: 0, k: [100, 100, 100] },
  },
  ao: 0,
  shapes: [
    {
      ty: "gr",
      it: [
        { ty: "rc", d: 1, s: { a: 0, k: [300, 4] }, p: { a: 0, k: [200, 192] }, r: { a: 0, k: 2 }, nm: "r" },
        { ty: "fl", c: { a: 0, k: BAR_COLOR }, o: { a: 0, k: 100 }, r: 1, nm: "f" },
        {
          ty: "tr",
          p: { a: 0, k: [0, 0] },
          a: { a: 0, k: [0, 0] },
          s: { a: 0, k: [100, 100] },
          r: { a: 0, k: 0 },
          o: { a: 0, k: 100 },
        },
      ],
      nm: "g",
    },
  ],
  ip: 0,
  op: OP,
  st: 0,
  bm: 0,
};

// Layer array order = paint order (first = on top): coin, bars, baseline.
export const compoundingLottie: Record<string, unknown> = {
  v: "5.7.4",
  fr: 30,
  ip: 0,
  op: OP,
  w: 400,
  h: 220,
  nm: "Compounding",
  ddd: 0,
  assets: [],
  layers: [coinLayer, ...BARS.map((b, i) => barLayer(b, i + 1)), baselineLayer],
};
