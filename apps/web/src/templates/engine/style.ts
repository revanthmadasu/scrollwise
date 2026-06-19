/**
 * Compile a node's StyleSpec into a className + inline CSS. The DB never carries
 * raw CSS/JS — only (a) a `preset` naming a vetted class in index.css, (b)
 * whitelisted layout tokens mapped here to a fixed CSS table, and (c) palette
 * tokens resolved to CSS variables. Nothing else can reach the DOM.
 */
import type { CSSProperties } from "react";
import type { PaletteToken, StyleSpec } from "./spec";

const SCALE: Record<string, string> = { sm: "8px", md: "14px", lg: "20px" };
const RADIUS: Record<string, string> = { sm: "8px", md: "12px", lg: "18px" };
const ALIGN: Record<string, string> = {
  start: "flex-start", center: "center", end: "flex-end", stretch: "stretch",
};
const JUSTIFY: Record<string, string> = {
  start: "flex-start", center: "center", end: "flex-end", between: "space-between",
};

const PALETTE_VAR: Record<PaletteToken, string> = {
  $accent: "var(--accent)",
  $bg: "var(--bg)",
  $surface: "var(--surface)",
  $text: "var(--text)",
  $cycle: "", // resolved against the cycle palette + repeat index
};

export interface StyleCtx {
  /** Cycle palette for the `$cycle` token. */
  accents?: string[];
  /** Current repeat index, drives `$cycle`. */
  index?: number;
}

/** Resolve a color-ish style value: palette token → CSS var/cycle color, else literal. */
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
  const style: CSSProperties = {};

  if (spec.dir) {
    style.display = "flex";
    style.flexDirection = spec.dir === "col" ? "column" : "row";
  }
  if (spec.gap) style.gap = SCALE[spec.gap];
  if (spec.pad) style.padding = SCALE[spec.pad];
  if (spec.radius) style.borderRadius = RADIUS[spec.radius];
  if (spec.align) style.alignItems = ALIGN[spec.align];
  if (spec.justify) style.justifyContent = JUSTIFY[spec.justify];
  if (spec.bg) style.background = resolveColor(spec.bg, ctx);
  if (spec.fg) style.color = resolveColor(spec.fg, ctx);

  if (spec.vars) {
    const styleRecord = style as Record<string, string | undefined>;
    for (const [name, token] of Object.entries(spec.vars)) {
      // Only allow custom-property names (must start with --).
      if (name.startsWith("--")) styleRecord[name] = resolveColor(token, ctx);
    }
  }

  return { className: spec.preset ?? "", style };
}
