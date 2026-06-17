import type { CSSProperties } from "react";
import { useTheme } from "../theme/ThemeContext";
import type { TemplateMeta } from "./types";

/**
 * Resolves a template's palette against the app's current light/dark mode and
 * returns the accent (with optional per-post override) plus the inline style
 * that injects the CSS variables every template's styles key off of.
 */
export function useTemplatePalette(meta: TemplateMeta, accentColor?: string) {
  const { resolved } = useTheme();
  const colors = meta.palette[resolved];
  const accent = accentColor ?? colors.accent;
  const style = {
    "--accent": accent,
    "--bg": colors.bg,
    "--surface": colors.surface,
    "--text": colors.text,
  } as CSSProperties;
  return { accent, style };
}
