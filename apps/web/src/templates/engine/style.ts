/**
 * Compile a node's StyleSpec into a className + inline CSS. The DB never carries
 * raw CSS/JS — only (a) a `preset` naming a vetted class in index.css, (b)
 * whitelisted layout/typography tokens mapped here to a fixed CSS table, and (c)
 * palette tokens resolved to CSS variables. Nothing else can reach the DOM.
 */
import type { CSSProperties } from "react";
import type { PaletteToken, StyleSpec } from "./spec";

const SCALE: Record<string, string> = { xs: "4px", sm: "8px", md: "14px", lg: "20px", xl: "32px" };
const RADIUS: Record<string, string> = { none: "0", xs: "4px", sm: "8px", md: "12px", lg: "18px", xl: "26px", full: "999px" };
const FONT: Record<string, string> = {
  xs: "12px", sm: "14px", md: "16px", lg: "20px", xl: "26px",
  "2xl": "34px", "3xl": "44px", "4xl": "56px",
};
const ALIGN: Record<string, string> = {
  start: "flex-start", center: "center", end: "flex-end", stretch: "stretch", baseline: "baseline",
};
const JUSTIFY: Record<string, string> = {
  start: "flex-start", center: "center", end: "flex-end", between: "space-between", around: "space-around",
};
const TRACKING: Record<string, string> = { tight: "-0.02em", normal: "0", wide: "0.04em", wider: "0.12em" };
const LEADING: Record<string, string> = { tight: "1.15", normal: "1.5", loose: "1.8" };
const SHADOW: Record<string, string> = {
  sm: "0 1px 3px rgba(0,0,0,0.18)", md: "0 6px 20px rgba(0,0,0,0.22)", lg: "0 16px 48px rgba(0,0,0,0.30)",
};
const SERIF = "Georgia, 'Times New Roman', serif";
const MONO = "ui-monospace, 'SF Mono', Menlo, monospace";

const PALETTE_VAR: Record<PaletteToken, string> = {
  $accent: "var(--accent)", $bg: "var(--bg)", $surface: "var(--surface)", $text: "var(--text)",
  $cycle: "",
};

export interface StyleCtx {
  accents?: string[];
  index?: number;
}

function resolveColor(token: string | undefined, ctx: StyleCtx): string | undefined {
  if (!token) return undefined;
  if (token === "$cycle") {
    const arr = ctx.accents;
    if (arr && arr.length) return arr[(ctx.index ?? 0) % arr.length];
    return "var(--accent)";
  }
  if (token in PALETTE_VAR) return PALETTE_VAR[token as PaletteToken] || undefined;
  return token; // literal hex/color
}

export function compileStyle(
  spec: StyleSpec | undefined,
  ctx: StyleCtx,
): { className: string; style: CSSProperties } {
  if (!spec) return { className: "", style: {} };
  const s: CSSProperties = {};
  const rec = s as Record<string, string | number | undefined>;

  // layout
  if (spec.dir) { s.display = "flex"; s.flexDirection = spec.dir === "col" ? "column" : "row"; }
  if (spec.gap) s.gap = SCALE[spec.gap];
  if (spec.pad) s.padding = SCALE[spec.pad];
  if (spec.padX) { s.paddingLeft = SCALE[spec.padX]; s.paddingRight = SCALE[spec.padX]; }
  if (spec.padY) { s.paddingTop = SCALE[spec.padY]; s.paddingBottom = SCALE[spec.padY]; }
  if (spec.radius) s.borderRadius = RADIUS[spec.radius];
  if (spec.align) s.alignItems = ALIGN[spec.align];
  if (spec.justify) s.justifyContent = JUSTIFY[spec.justify];
  if (spec.wrap) s.flexWrap = "wrap";
  if (spec.grow != null) s.flexGrow = spec.grow;
  if (spec.w) s.width = spec.w === "full" ? "100%" : spec.w === "half" ? "50%" : "auto";
  if (spec.h != null) s.height = spec.h === "full" ? "100%" : spec.h === "auto" ? "auto" : `${Number(spec.h)}px`;
  if (spec.minH != null) s.minHeight = `${Number(spec.minH)}px`;

  // color
  if (spec.bg) s.background = resolveColor(spec.bg, ctx);
  if (spec.fg) s.color = resolveColor(spec.fg, ctx);
  if (spec.border) { s.borderStyle = "solid"; s.borderWidth = `${spec.borderWidth ?? 1}px`; s.borderColor = resolveColor(spec.border, ctx); }
  if (spec.accentBar) {
    const color = resolveColor(spec.border, ctx) ?? "var(--accent)";
    const side = spec.accentBar[0].toUpperCase() + spec.accentBar.slice(1);
    rec[`border${side}`] = `${spec.borderWidth ?? 3}px solid ${color}`;
  }
  if (spec.opacity != null) s.opacity = spec.opacity;
  if (spec.shadow) s.boxShadow = SHADOW[spec.shadow];

  // typography
  if (spec.size) s.fontSize = FONT[spec.size];
  if (spec.weight) s.fontWeight = spec.weight;
  if (spec.talign) s.textAlign = spec.talign;
  if (spec.transform === "upper") s.textTransform = "uppercase";
  if (spec.tracking) s.letterSpacing = TRACKING[spec.tracking];
  if (spec.leading) s.lineHeight = LEADING[spec.leading];
  if (spec.italic) s.fontStyle = "italic";
  if (spec.serif) s.fontFamily = SERIF;
  if (spec.mono) s.fontFamily = MONO;

  // media
  if (spec.fit) s.objectFit = spec.fit;

  // positioning
  if (spec.pos) s.position = spec.pos;
  if (spec.inset) {
    if (spec.inset.top != null) s.top = `${Number(spec.inset.top)}px`;
    if (spec.inset.right != null) s.right = `${Number(spec.inset.right)}px`;
    if (spec.inset.bottom != null) s.bottom = `${Number(spec.inset.bottom)}px`;
    if (spec.inset.left != null) s.left = `${Number(spec.inset.left)}px`;
  }
  if (spec.z != null) s.zIndex = Number(spec.z);

  if (spec.vars) {
    for (const [name, token] of Object.entries(spec.vars)) {
      if (name.startsWith("--")) rec[name] = resolveColor(token, ctx);
    }
  }

  return { className: spec.preset ?? "", style: s };
}
