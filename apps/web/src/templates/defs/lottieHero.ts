import type { TemplateDoc } from "../engine/spec";
import { compoundingLottie } from "../assets/compoundingLottie";

/** Full-bleed Lottie animation as hero. Playful and dynamic — short supporting text. */
export const lottieHero: TemplateDoc = {
  template_id: "lottie-hero",
  name: "LottieHero",
  version: 1,
  engine: 1,
  vibe: "playful",
  description: "Full-bleed Lottie animation as hero. Playful and dynamic — short supporting text only.",
  content_types: ["text", "image_post"],
  palette: {
    dark: { accent: "#fbbf24", bg: "#0f0d00", surface: "#1a1700", text: "#fef9e7" },
    light: { accent: "#d97706", bg: "#fffbeb", surface: "#fef3c7", text: "#78350f" },
  },
  fields: [
    { name: "title", type: "text", required: true, max: 60 },
    { name: "lottie", type: "asset", asset: "lottie", required: true },
    { name: "subtitle", type: "text", max: 100 },
    { name: "body", type: "rich", max: 240 },
    { name: "bullets", type: "list", max: 3, item: { name: "bullet", type: "text", max: 120 } },
    { name: "accentColor", type: "color" },
  ],
  layout: {
    type: "box",
    style: { preset: "tmpl-lottie-hero" },
    children: [
      {
        type: "box",
        when: "lottie",
        style: { preset: "lh-lottie-wrap" },
        children: [
          { type: "lottie", style: { preset: "lh-lottie" }, src: { $bind: "lottie.src" }, loop: true },
        ],
      },
      { type: "box", unless: "lottie", style: { preset: "lh-lottie-placeholder" } },
      {
        type: "box",
        style: { preset: "lh-content" },
        children: [
          { type: "deco", variant: "playful", seed: { $bind: "title" } },
          { type: "text", as: "h2", style: { preset: "lh-title" }, value: { $bind: "title" } },
          { type: "text", as: "p", when: "subtitle", style: { preset: "lh-subtitle" }, value: { $bind: "subtitle" } },
          { type: "text", as: "p", when: "body", style: { preset: "lh-body" }, value: { $bind: "body" } },
          {
            type: "repeat",
            over: "bullets",
            as: "b",
            when: { $bind: "bullets.0" },
            wrap: { as: "ul", style: { preset: "lh-bullets" } },
            child: {
              type: "box",
              as: "li",
              style: { preset: "lh-bullet" },
              children: [
                { type: "box", as: "span", style: { preset: "lh-dot", bg: "$accent" } },
                { type: "text", as: "span", value: { $bind: "b" } },
              ],
            },
          },
        ],
      },
    ],
  },
  sample: {
    title: "Compounding: The Eighth Wonder",
    subtitle: "Why starting at 22 beats starting at 32",
    body: "10 years of compounding at 8% doubles your money. 30 years turns $10k into $100k. Time is the variable nobody sells you.",
    bullets: [
      "$1 at 25 → $21 at 65 (at 8%)",
      "Warren Buffett earned 97% of his wealth after 65",
    ],
    lottie: { id: "compounding-growth", src: compoundingLottie },
  },
};
