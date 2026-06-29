import type { TemplateDoc } from "../engine/spec";

/** Clean layout for long-form reading. Calm, intellectual — highest body capacity. */
export const minimalScroll: TemplateDoc = {
  template_id: "minimal-scroll",
  name: "MinimalScroll",
  version: 1,
  engine: 1,
  vibe: "calm",
  description: "Clean serif layout for long-form reading. Calm, intellectual — highest body capacity.",
  content_types: ["text", "carousel"],
  palette: {
    dark: { accent: "#6ee7b7", bg: "#0c0f0e", surface: "#111714", text: "#e2f5ee" },
    light: { accent: "#059669", bg: "#f5faf8", surface: "#ecfdf5", text: "#064e3b" },
  },
  fields: [
    { name: "title", type: "text", required: true, max: 80 },
    { name: "body", type: "rich", required: true, max: 800 },
    { name: "subtitle", type: "text", max: 120 },
    { name: "bullets", type: "list", max: 6, item: { name: "bullet", type: "text", max: 120 } },
    { name: "images", type: "list", max: 2, of: [
      { name: "url", type: "asset", asset: "image", required: true },
      { name: "alt", type: "text", max: 120 },
    ] },
    { name: "svg", type: "asset", asset: "svg" },
    { name: "accentColor", type: "color" },
  ],
  layout: {
    type: "box",
    style: { preset: "tmpl-minimal-scroll" },
    children: [
      { type: "box", style: { preset: "ms-accent-line" } },
      { type: "deco", variant: "minimal", seed: { $bind: "title" } },
      {
        type: "box",
        as: "header",
        style: { preset: "ms-header" },
        children: [
          { type: "text", as: "h2", style: { preset: "ms-title" }, value: { $bind: "title" } },
          { type: "text", as: "p", when: "subtitle", style: { preset: "ms-subtitle" }, value: { $bind: "subtitle" } },
        ],
      },
      { type: "svg", when: "svg", style: { preset: "ms-svg-slot" }, markup: { $bind: "svg.markup" } },
      {
        type: "repeat",
        over: "images",
        as: "img",
        when: { $bind: "images.0" },
        wrap: { style: { preset: "ms-images" } },
        child: { type: "image", style: { preset: "ms-image" }, src: { $bind: "img.url" }, alt: { $bind: "img.alt" } },
      },
      { type: "text", as: "p", when: "body", style: { preset: "ms-body" }, value: { $bind: "body" } },
      {
        type: "repeat",
        over: "bullets",
        as: "b",
        when: { $bind: "bullets.0" },
        wrap: { as: "ul", style: { preset: "ms-bullets" } },
        child: { type: "text", as: "li", style: { preset: "ms-bullet" }, value: { $bind: "b" } },
      },
    ],
  },
  sample: {
    title: "The Stoic Practice of Negative Visualization",
    subtitle: "Premeditatio Malorum — imagining the worst to appreciate the present",
    body: "Stoic philosophers deliberately pictured losing what they valued most — health, relationships, freedom — not to dwell in despair, but to dissolve the numbness of familiarity. When you imagine your morning coffee as if it might be your last, it tastes different. Seneca called this the antidote to entitlement. The practice interrupts hedonic adaptation: the psychological tendency to take good things for granted the moment they become routine. Five minutes of negative visualization can restore gratitude that months of abundance eroded.",
    bullets: [
      "Seneca wrote letters on this practice daily",
      "Modern psychology calls it 'prospective hindsight'",
      "Works best first thing in the morning",
    ],
  },
};
