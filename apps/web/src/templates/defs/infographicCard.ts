import type { TemplateDoc } from "../engine/spec";

/** Data-first layout with stat blocks and optional SVG diagram. Structured and analytical. */
export const infographicCard: TemplateDoc = {
  template_id: "infographic-card",
  name: "InfographicCard",
  version: 1,
  engine: 1,
  vibe: "structured",
  description: "Data-first layout with stat blocks and optional SVG diagram. Structured and analytical.",
  content_types: ["text", "image_post"],
  palette: {
    dark: { accent: "#38bdf8", bg: "#03080f", surface: "#0a1520", text: "#e0f2fe" },
    light: { accent: "#0284c7", bg: "#f0f9ff", surface: "#e0f2fe", text: "#0c4a6e" },
  },
  // Per-stat accent cycle (drives the `$cycle` token in the stats repeat).
  accents: ["#38bdf8", "#818cf8", "#34d399", "#f472b6", "#fb923c"],
  fields: [
    { name: "title", type: "text", required: true, max: 70 },
    { name: "stats", type: "list", required: true, min: 1, max: 5, of: [
      { name: "label", type: "text", required: true, max: 24 },
      { name: "value", type: "text", required: true, max: 12 },
      { name: "unit", type: "text", max: 8 },
    ] },
    { name: "subtitle", type: "text", max: 100 },
    { name: "body", type: "rich", max: 200 },
    { name: "images", type: "list", max: 1, of: [
      { name: "url", type: "asset", asset: "image", required: true },
      { name: "alt", type: "text", max: 120 },
    ] },
    { name: "svg", type: "asset", asset: "svg" },
    { name: "accentColor", type: "color" },
  ],
  layout: {
    type: "box",
    style: { preset: "tmpl-infographic-card" },
    children: [
      { type: "deco", variant: "structured", seed: { $bind: "title" } },
      {
        type: "box",
        as: "header",
        style: { preset: "ic-header" },
        children: [
          { type: "image", when: { $bind: "images.0" }, style: { preset: "ic-thumb" }, src: { $bind: "images.0.url" }, alt: { $bind: "images.0.alt" } },
          {
            type: "box",
            children: [
              { type: "text", as: "h2", style: { preset: "ic-title" }, value: { $bind: "title" } },
              { type: "text", as: "p", when: "subtitle", style: { preset: "ic-subtitle" }, value: { $bind: "subtitle" } },
            ],
          },
        ],
      },
      {
        type: "repeat",
        over: "stats",
        as: "stat",
        when: { $bind: "stats.0" },
        wrap: { style: { preset: "ic-stats" } },
        child: {
          type: "box",
          style: { preset: "ic-stat", vars: { "--stat-color": "$cycle" } },
          children: [
            { type: "text", as: "span", style: { preset: "ic-stat-value" }, value: { $bind: "stat.value" } },
            { type: "text", as: "span", when: { $bind: "stat.unit" }, style: { preset: "ic-stat-unit" }, value: { $bind: "stat.unit" } },
            { type: "text", as: "span", style: { preset: "ic-stat-label" }, value: { $bind: "stat.label" } },
          ],
        },
      },
      { type: "svg", when: "svg", style: { preset: "ic-svg-slot" }, markup: { $bind: "svg.markup" } },
      { type: "text", as: "p", when: "body", style: { preset: "ic-body" }, value: { $bind: "body" } },
    ],
  },
  sample: {
    title: "The Human Brain at a Glance",
    subtitle: "Key numbers every learner should know",
    stats: [
      { label: "Neurons", value: "86B" },
      { label: "Synapses", value: "100T" },
      { label: "Processing speed", value: "120", unit: "m/s" },
      { label: "Memory capacity", value: "2.5", unit: "PB" },
      { label: "Energy use", value: "20", unit: "W" },
    ],
    body: "Your brain runs on less power than a dim light bulb yet outperforms any computer at pattern recognition and abstraction.",
  },
};
