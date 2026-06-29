import type { TemplateDoc } from "../engine/spec";

/** Neon glow border with pulsing accent — high energy, short punchy content. */
export const glowPulse: TemplateDoc = {
  template_id: "glow-pulse",
  name: "GlowPulse",
  version: 1,
  engine: 1,
  vibe: "energetic",
  description: "Neon glow border with pulsing accent — high energy, short punchy content.",
  content_types: ["text", "image_post"],
  palette: {
    dark: { accent: "#a855f7", bg: "#0a0a0f", surface: "#13101f", text: "#f0e6ff" },
    light: { accent: "#7c3aed", bg: "#faf5ff", surface: "#f3e8ff", text: "#2e1065" },
  },
  fields: [
    { name: "title", type: "text", required: true, max: 60 },
    { name: "subtitle", type: "text", max: 100 },
    { name: "body", type: "rich", max: 280 },
    { name: "bullets", type: "list", max: 4, item: { name: "bullet", type: "text", max: 120 } },
    { name: "images", type: "list", max: 1, of: [
      { name: "url", type: "asset", asset: "image", required: true },
      { name: "alt", type: "text", max: 120 },
    ] },
    { name: "accentColor", type: "color" },
  ],
  layout: {
    type: "box",
    style: { preset: "tmpl-glow-pulse" },
    children: [
      { type: "box", style: { preset: "gp-glow-ring" } },
      { type: "deco", variant: "glow", seed: { $bind: "title" } },
      {
        type: "box",
        when: { $bind: "images.0" },
        style: { preset: "gp-image-wrap" },
        children: [
          { type: "image", style: { preset: "gp-image" }, src: { $bind: "images.0.url" }, alt: { $bind: "images.0.alt" } },
          { type: "box", style: { preset: "gp-image-overlay" } },
        ],
      },
      {
        type: "box",
        style: { preset: "gp-content" },
        children: [
          { type: "text", as: "h2", style: { preset: "gp-title" }, value: { $bind: "title" } },
          { type: "text", as: "p", when: "subtitle", style: { preset: "gp-subtitle" }, value: { $bind: "subtitle" } },
          { type: "text", as: "p", when: "body", style: { preset: "gp-body" }, value: { $bind: "body" } },
          {
            type: "repeat",
            over: "bullets",
            as: "b",
            when: { $bind: "bullets.0" },
            wrap: { as: "ul", style: { preset: "gp-bullets" } },
            child: {
              type: "box",
              as: "li",
              style: { preset: "gp-bullet" },
              children: [
                { type: "box", as: "span", style: { preset: "gp-bullet-dot" } },
                { type: "text", as: "span", value: { $bind: "b" } },
              ],
            },
          },
        ],
      },
      { type: "box", style: { preset: "gp-pulse-bar" } },
    ],
  },
  sample: {
    title: "Why Black Holes Bend Time",
    subtitle: "General relativity's wildest prediction",
    body: "Mass curves spacetime so severely near a black hole that time itself slows. A clock at the event horizon would appear frozen to a distant observer.",
    bullets: [
      "Time dilation is measurable even on Earth (GPS satellites)",
      "At the event horizon, time stops relative to outside",
      "Hawking radiation slowly evaporates black holes over eons",
    ],
  },
};
