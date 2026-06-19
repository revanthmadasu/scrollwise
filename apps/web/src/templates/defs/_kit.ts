/**
 * Authoring kit for the template library: node-builder helpers, field-spec
 * presets, a palette catalog, and sample content. Keeps each distinct layout
 * in library.ts compact and readable. Pure data — no React.
 */
import type {
  BoxNode, DecoNode, Field, ImageNode, LayoutNode, LottieNode, RepeatNode,
  StyleSpec, SvgNode, TextNode, ThemePalette, Value,
} from "../engine/spec";

// --- node builders ----------------------------------------------------------

export const bind = (path: string) => ({ $bind: path });

export function box(style: StyleSpec, children?: LayoutNode[], extra: Partial<BoxNode> = {}): BoxNode {
  return { type: "box", style, ...(children ? { children } : {}), ...extra };
}
export function txt(value: Value<string>, style?: StyleSpec, extra: Partial<TextNode> = {}): TextNode {
  return { type: "text", value, ...(style ? { style } : {}), ...extra };
}
export function img(src: Value<string>, style?: StyleSpec, extra: Partial<ImageNode> = {}): ImageNode {
  return { type: "image", src, ...(style ? { style } : {}), ...extra };
}
export function deco(variant: DecoNode["variant"], seed?: Value<string>): DecoNode {
  return { type: "deco", variant, ...(seed ? { seed } : {}) };
}
export function svg(markup: Value<string>, style?: StyleSpec, extra: Partial<SvgNode> = {}): SvgNode {
  return { type: "svg", markup, ...(style ? { style } : {}), ...extra };
}
export function lottie(src: Value<string | Record<string, unknown>>, style?: StyleSpec, extra: Partial<LottieNode> = {}): LottieNode {
  return { type: "lottie", src, ...(style ? { style } : {}), ...extra };
}
export function rep(over: string, as: string, child: LayoutNode, wrap?: RepeatNode["wrap"], extra: Partial<RepeatNode> = {}): RepeatNode {
  return { type: "repeat", over, as, child, ...(wrap ? { wrap } : {}), ...extra };
}

// --- field-spec presets (content-length is just different maxes) ------------

export const F = {
  title: (max = 70): Field => ({ name: "title", type: "text", required: true, max }),
  subtitle: (max = 100): Field => ({ name: "subtitle", type: "text", max }),
  body: (max = 300): Field => ({ name: "body", type: "rich", max }),
  bullets: (max = 4): Field => ({ name: "bullets", type: "list", max, item: { name: "bullet", type: "text", max: 120 } }),
  stats: (max = 4): Field => ({ name: "stats", type: "list", max, of: [
    { name: "label", type: "text", max: 24, required: true },
    { name: "value", type: "text", max: 12, required: true },
    { name: "unit", type: "text", max: 8 },
  ] }),
  steps: (max = 5): Field => ({ name: "steps", type: "list", max, of: [
    { name: "title", type: "text", max: 40, required: true },
    { name: "text", type: "text", max: 160 },
  ] }),
  image: (): Field => ({ name: "images", type: "list", max: 1, of: [
    { name: "url", type: "asset", asset: "image", required: true },
    { name: "alt", type: "text", max: 120 },
  ] }),
  svg: (): Field => ({ name: "svg", type: "asset", asset: "svg" }),
  lottie: (): Field => ({ name: "lottie", type: "asset", asset: "lottie", required: true }),
  accent: (): Field => ({ name: "accentColor", type: "color" }),
};

// --- palette catalog (color themes; each has light + dark) -------------------

const P = (
  la: string, lbg: string, lsf: string, lt: string,
  da: string, dbg: string, dsf: string, dt: string,
): ThemePalette => ({
  light: { accent: la, bg: lbg, surface: lsf, text: lt },
  dark: { accent: da, bg: dbg, surface: dsf, text: dt },
});

export const PALETTES: Record<string, ThemePalette> = {
  ocean: P("#0284c7", "#f0f9ff", "#e0f2fe", "#0c4a6e", "#38bdf8", "#03080f", "#0a1520", "#e0f2fe"),
  forest: P("#059669", "#f5faf8", "#ecfdf5", "#064e3b", "#6ee7b7", "#0c0f0e", "#111714", "#e2f5ee"),
  sunset: P("#ea580c", "#fff7ed", "#ffedd5", "#7c2d12", "#fb923c", "#1a0e06", "#241405", "#ffe8d6"),
  gold: P("#d97706", "#fffbeb", "#fef3c7", "#78350f", "#fbbf24", "#0f0d00", "#1a1700", "#fef9e7"),
  berry: P("#be185d", "#fdf2f8", "#fce7f3", "#831843", "#f472b6", "#160510", "#240a1a", "#fce7f3"),
  violet: P("#7c3aed", "#faf5ff", "#f3e8ff", "#2e1065", "#a855f7", "#0a0a0f", "#13101f", "#f0e6ff"),
  slate: P("#475569", "#f8fafc", "#eef2f7", "#1e293b", "#94a3b8", "#0a0e14", "#141a24", "#e2e8f0"),
  ink: P("#1f2937", "#fafaf9", "#f1f0ec", "#111827", "#d1d5db", "#0b0b0d", "#16161a", "#f3f4f6"),
  mint: P("#0d9488", "#f0fdfa", "#ccfbf1", "#134e4a", "#5eead4", "#04120f", "#0a1f1b", "#d5f5ee"),
  coral: P("#e11d48", "#fff1f2", "#ffe4e6", "#881337", "#fb7185", "#160508", "#260a0e", "#ffe4e6"),
  sky: P("#2563eb", "#eff6ff", "#dbeafe", "#1e3a8a", "#60a5fa", "#070b16", "#0e1626", "#dbeafe"),
  sand: P("#a16207", "#fefce8", "#fef9c3", "#713f12", "#d4a35a", "#13110a", "#211c10", "#f4ead0"),
  cosmos: P("#6366f1", "#eef2ff", "#e0e7ff", "#312e81", "#818cf8", "#05060f", "#0c1024", "#e0e7ff"),
  chalk: P("#0f766e", "#f0fdf4", "#dcfce7", "#14532d", "#86efac", "#0a1410", "#13241a", "#e6f7ec"),
  ember: P("#b91c1c", "#fef2f2", "#fee2e2", "#7f1d1d", "#f87171", "#140505", "#220a0a", "#fee2e2"),
  candy: P("#db2777", "#fdf4ff", "#fae8ff", "#701a75", "#e879f9", "#12041a", "#220a2e", "#fae8ff"),
};

// --- sample images (inline data-URIs so previews don't depend on any asset) -

const _img = (accent: string, bg: string): string =>
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 240'>` +
    `<rect width='400' height='240' fill='${bg}'/>` +
    `<circle cx='300' cy='70' r='90' fill='${accent}' opacity='0.45'/>` +
    `<circle cx='110' cy='185' r='55' fill='${accent}' opacity='0.30'/>` +
    `<circle cx='210' cy='120' r='28' fill='${accent}' opacity='0.55'/></svg>`,
  );

export const SAMPLE_IMG = _img("#5b8cff", "#0b1026");
export const SAMPLE_IMG_BIO = _img("#56c26a", "#071508");

// --- sample content (a few flavors so previews read naturally) --------------

export const SAMPLE_TEXT = {
  title: "Why the Sky Is Blue",
  subtitle: "Rayleigh scattering, explained simply",
  long:
    "Sunlight contains every color, but air scatters short blue wavelengths far more than long red ones. So when you look anywhere away from the sun, you're seeing blue light bounced toward you from every direction. At sunset the light travels through more atmosphere, the blue scatters away entirely, and the reds survive.",
  short: "Air scatters blue light more than red — so the whole sky glows blue.",
  bullets: ["Blue scatters ~10× more than red", "Sunsets are red for the same reason", "Mars has blue sunsets — reversed"],
  steps: [
    { title: "White light enters", text: "Sunlight carries all colors at once." },
    { title: "Air scatters blue", text: "Tiny molecules deflect short wavelengths most." },
    { title: "Blue fills the sky", text: "Scattered light reaches your eye from everywhere." },
  ],
  stats: [
    { label: "Wavelength", value: "450", unit: "nm" },
    { label: "Scatter ∝", value: "1/λ⁴" },
    { label: "Sky temp", value: "10k", unit: "K" },
  ],
};
