/**
 * Template library — batch 2. More distinct layouts across vibes, scenes, age
 * groups and content lengths. Same engine + kit as library.ts.
 */
import type { TemplateDoc } from "../engine/spec";
import { F, PALETTES, SAMPLE_IMG, SAMPLE_TEXT, bind, box, deco, img, rep, txt } from "./_kit";

const S = SAMPLE_TEXT;

export const LIBRARY2: TemplateDoc[] = [
  // 21 — magazine editorial (large, calm)
  {
    template_id: "magazine", name: "Magazine", version: 1, engine: 1, vibe: "calm",
    description: "Editorial feature layout with a kicker, headline and lead. Long-form, refined.",
    content_types: ["text"], tags: ["editorial", "calm", "large", "adult"],
    palette: PALETTES.ink,
    fields: [F.title(80), F.subtitle(120), F.body(700), { name: "kicker", type: "text", max: 24 }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "sm", pad: "xl", bg: "$bg", fg: "$text", radius: "none" }, [
      txt(bind("kicker"), { transform: "upper", tracking: "wider", size: "xs", weight: 700, fg: "$accent" }, { as: "p", when: "kicker" }),
      txt(bind("title"), { serif: true, size: "3xl", weight: 700, leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { serif: true, italic: true, size: "lg", opacity: 0.75, leading: "normal" }, { as: "p", when: "subtitle" }),
      box({ preset: "te-rule-soft", w: "full", h: 2 }),
      txt(bind("body"), { serif: true, size: "md", leading: "loose" }, { as: "p", when: "body" }),
    ]),
    sample: { kicker: "Physics", title: "The Color of Everything", subtitle: "A short history of why we see what we see", body: S.long + " " + S.long },
  },

  // 22 — minimal mono (calm, lots of whitespace)
  {
    template_id: "minimal-mono", name: "MinimalMono", version: 1, engine: 1, vibe: "calm",
    description: "Spare monospace layout with generous whitespace. Quiet and modern.",
    content_types: ["text"], tags: ["minimal", "calm", "small", "adult"],
    palette: PALETTES.slate,
    fields: [F.title(60), F.subtitle(90), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "lg", pad: "xl", bg: "$bg", fg: "$text", radius: "lg", minH: 180, justify: "center" }, [
      txt("//", { mono: true, size: "md", fg: "$accent", weight: 700 }, { as: "span" }),
      txt(bind("title"), { size: "2xl", weight: 500, leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { mono: true, size: "sm", opacity: 0.65 }, { as: "p", when: "subtitle" }),
    ]),
    sample: { title: "Less, but better.", subtitle: "// signal over noise" },
  },

  // 23 — checklist
  {
    template_id: "checklist", name: "Checklist", version: 1, engine: 1, vibe: "structured",
    description: "A title with checkable items — takeaways and to-dos.",
    content_types: ["text"], tags: ["list", "structured", "medium", "tween"],
    palette: PALETTES.forest,
    fields: [F.title(60), F.bullets(6), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "xl", weight: 800 }, { as: "h2" }),
      rep("bullets", "b", box({ dir: "row", gap: "sm", align: "center" }, [
        box({ w: "auto", h: 18, minH: 18, border: "$accent", borderWidth: 2, radius: "xs", pad: "sm" }),
        txt(bind("b"), { size: "sm" }, { as: "span" }),
      ]), { style: { dir: "col", gap: "sm" } }, { when: { $bind: "bullets.0" } }),
    ]),
    sample: { title: "Before the exam, make sure you can…", bullets: ["State Rayleigh's 1/λ⁴ law", "Explain red sunsets", "Sketch a scattering diagram", "Name one everyday example"] },
  },

  // 24 — callout / tip box
  {
    template_id: "callout", name: "Callout", version: 1, engine: 1, vibe: "structured",
    description: "A highlighted tip or warning. Small, attention-grabbing aside.",
    content_types: ["text"], tags: ["callout", "structured", "small", "adult"],
    palette: PALETTES.gold,
    fields: [{ name: "title", type: "text", max: 24 }, F.body(180), F.accent()],
    layout: box({ preset: "te-card", dir: "row", gap: "md", pad: "lg", bg: "$surface", fg: "$text", radius: "md", accentBar: "left", borderWidth: 5, align: "start" }, [
      txt("!", { size: "lg", weight: 900, fg: "$bg", bg: "$accent", radius: "full", w: "auto", talign: "center", padX: "md", padY: "xs" }, { as: "span" }),
      box({ dir: "col", gap: "xs", grow: 1 }, [
        txt(bind("title"), { transform: "upper", tracking: "wide", size: "xs", weight: 800, fg: "$accent" }, { as: "p", when: "title" }),
        txt(bind("body"), { size: "sm", leading: "normal" }, { as: "p", when: "body" }),
      ]),
    ]),
    sample: { title: "Remember", body: "Scattering depends on 1/λ⁴ — halve the wavelength and you scatter 16× as much light." },
  },

  // 25 — recipe (ingredients + method)
  {
    template_id: "recipe", name: "Recipe", version: 1, engine: 1, vibe: "structured",
    description: "An ingredients list plus a numbered method. Procedures and experiments.",
    content_types: ["text", "carousel"], tags: ["steps", "structured", "large", "tween", "scene-lab"],
    palette: PALETTES.sunset,
    fields: [F.title(60), { name: "ingredients", type: "list", max: 6, item: { name: "i", type: "text", max: 60 } }, F.steps(5), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "xl", weight: 800 }, { as: "h2" }),
      txt("You'll need", { transform: "upper", tracking: "wide", size: "xs", weight: 800, fg: "$accent" }, { as: "p" }),
      rep("ingredients", "i", box({ dir: "row", gap: "sm", align: "center" }, [
        txt("•", { fg: "$accent", weight: 800 }, { as: "span" }),
        txt(bind("i"), { size: "sm" }, { as: "span" }),
      ]), { style: { dir: "col", gap: "xs" } }, { when: { $bind: "ingredients.0" } }),
      txt("Method", { transform: "upper", tracking: "wide", size: "xs", weight: 800, fg: "$accent" }, { as: "p" }),
      rep("steps", "s", box({ dir: "row", gap: "sm", align: "start" }, [
        txt(bind("$n"), { size: "sm", weight: 800, fg: "$bg", bg: "$accent", radius: "full", w: "auto", padX: "sm", padY: "xs" }, { as: "span" }),
        txt(bind("s.title"), { size: "sm", weight: 600 }, { as: "span" }),
      ]), { style: { dir: "col", gap: "sm" } }, { when: { $bind: "steps.0" } }),
    ]),
    sample: { title: "See scattering at home", ingredients: ["A clear glass of water", "A few drops of milk", "A flashlight"], steps: S.steps },
  },

  // 26 — level up (gamified)
  {
    template_id: "level-up", name: "LevelUp", version: 1, engine: 1, vibe: "playful",
    description: "A gamified progress card with a level badge and XP bar. Motivating, teen.",
    content_types: ["text"], tags: ["gamified", "playful", "small", "teen"],
    palette: PALETTES.candy,
    fields: [{ name: "title", type: "text", required: true, max: 40 }, { name: "level", type: "text", max: 8 }, F.subtitle(80), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", border: "$accent", borderWidth: 2 }, [
      box({ dir: "row", gap: "sm", align: "center", justify: "between" }, [
        txt(bind("title"), { size: "lg", weight: 800 }, { as: "h2" }),
        txt(bind("level"), { size: "xs", weight: 900, transform: "upper", tracking: "wide", fg: "$bg", bg: "$accent", radius: "full", padX: "sm", padY: "xs" }, { as: "span", when: "level" }),
      ]),
      txt(bind("subtitle"), { size: "sm", opacity: 0.8 }, { as: "p", when: "subtitle" }),
      box({ w: "full", h: 12, minH: 12, bg: "$surface", radius: "full" }, [
        box({ w: "half", h: 12, minH: 12, bg: "$accent", radius: "full", preset: "te-pulse" }),
      ]),
    ]),
    sample: { title: "Optics mastery", level: "Lv 3", subtitle: "2 more lessons to level up" },
  },

  // 27 — comic panel (kids/teen)
  {
    template_id: "comic-panel", name: "ComicPanel", version: 1, engine: 1, vibe: "playful",
    description: "A bold comic-book panel with a punchy caption. Fun and loud.",
    content_types: ["text", "image_post"], tags: ["kids", "playful", "small", "scene-city"],
    palette: PALETTES.ember,
    fields: [F.title(40), F.subtitle(80), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$surface", fg: "$text", radius: "md", border: "$text", borderWidth: 4, minH: 170, justify: "between" }, [
      deco("playful", bind("title")),
      txt(bind("title"), { size: "3xl", weight: 900, transform: "upper", leading: "tight", fg: "$accent" }, { as: "h2" }),
      txt(bind("subtitle"), { size: "md", weight: 700, bg: "$accent", fg: "#ffffff", padX: "sm", padY: "xs", radius: "sm" }, { as: "span", when: "subtitle" }),
    ]),
    sample: { title: "Zap! Light splits!", subtitle: "…and the sky goes blue" },
  },

  // 28 — polaroid
  {
    template_id: "polaroid", name: "Polaroid", version: 1, engine: 1, vibe: "playful",
    description: "A framed photo with a handwritten caption. Personal and warm.",
    content_types: ["image_post"], tags: ["image", "playful", "small", "adult"],
    palette: PALETTES.ink,
    fields: [F.title(50), F.image(), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "md", align: "center" }, [
      box({ bg: "#ffffff", pad: "sm", radius: "xs", shadow: "md", w: "full" }, [
        img(bind("images.0.url"), { w: "full", h: 150, fit: "cover" }, { when: { $bind: "images.0" }, alt: bind("images.0.alt") }),
      ]),
      txt(bind("title"), { serif: true, italic: true, size: "lg", talign: "center" }, { as: "p" }),
    ]),
    sample: { title: "Caught the sky mid-scatter ✦", images: [{ url: SAMPLE_IMG, alt: "sky" }] },
  },

  // 29 — fact strip
  {
    template_id: "fact-strip", name: "FactStrip", version: 1, engine: 1, vibe: "energetic",
    description: "A single surprising fact with a bold banner. Snackable and punchy.",
    content_types: ["text"], tags: ["fact", "energetic", "small", "tween"],
    palette: PALETTES.sky,
    fields: [F.body(160), { name: "title", type: "text", max: 20 }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { transform: "upper", tracking: "wider", size: "sm", weight: 900, fg: "#ffffff", bg: "$accent", padX: "lg", padY: "md", w: "full" }, { as: "p" }),
      txt(bind("body"), { size: "lg", weight: 700, leading: "normal", pad: "lg" }, { as: "p" }),
    ]),
    sample: { title: "Did you know", body: "Mars has blue sunsets — its fine dust scatters light the opposite way to Earth's air." },
  },

  // 30 — profile / figure card (history)
  {
    template_id: "profile-card", name: "ProfileCard", version: 1, engine: 1, vibe: "calm",
    description: "A portrait, name, dates and short bio. People and history.",
    content_types: ["text", "image_post"], tags: ["history", "calm", "medium", "adult"],
    palette: PALETTES.sand,
    fields: [F.title(40), F.subtitle(40), F.body(220), F.image(), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      box({ dir: "row", gap: "md", align: "center" }, [
        img(bind("images.0.url"), { w: "auto", h: 64, fit: "cover", radius: "full" }, { when: { $bind: "images.0" }, alt: bind("images.0.alt") }),
        box({ dir: "col", gap: "xs" }, [
          txt(bind("title"), { serif: true, size: "xl", weight: 700 }, { as: "h2" }),
          txt(bind("subtitle"), { size: "sm", fg: "$accent", weight: 600 }, { as: "p", when: "subtitle" }),
        ]),
      ]),
      txt(bind("body"), { serif: true, size: "sm", leading: "loose", opacity: 0.9 }, { as: "p", when: "body" }),
    ]),
    sample: { title: "Lord Rayleigh", subtitle: "1842 – 1919", body: "British physicist who explained why the sky is blue and later won the Nobel Prize for discovering argon.", images: [{ url: SAMPLE_IMG, alt: "portrait" }] },
  },

  // 31 — poll / multiple choice
  {
    template_id: "poll", name: "Poll", version: 1, engine: 1, vibe: "playful",
    description: "A question with selectable options. Interactive-feeling, teen.",
    content_types: ["text"], tags: ["quiz", "playful", "medium", "teen"],
    palette: PALETTES.violet,
    fields: [{ name: "title", type: "text", required: true, max: 90 }, { name: "options", type: "list", required: true, max: 4, item: { name: "o", type: "text", max: 60 } }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "lg", weight: 700, leading: "tight" }, { as: "h2" }),
      rep("options", "o", box({ dir: "row", gap: "sm", align: "center", border: "$accent", borderWidth: 1, radius: "md", padX: "md", padY: "sm" }, [
        txt(bind("$n"), { size: "sm", weight: 800, fg: "$accent" }, { as: "span" }),
        txt(bind("o"), { size: "sm" }, { as: "span" }),
      ]), { style: { dir: "col", gap: "sm" } }),
    ]),
    sample: { title: "Why is the sky blue?", options: ["The ocean reflects up", "Air scatters blue light", "The sun is blue", "Blue gas in the sky"] },
  },

  // 32 — legend / key (structured)
  {
    template_id: "legend", name: "Legend", version: 1, engine: 1, vibe: "structured",
    description: "A color-keyed legend of categories. Maps, charts and taxonomies.",
    content_types: ["text", "image_post"], tags: ["legend", "structured", "small", "adult"],
    palette: PALETTES.mint, accents: ["#5eead4", "#38bdf8", "#a855f7", "#fb923c", "#f472b6"],
    fields: [F.title(50), { name: "items", type: "list", required: true, max: 5, of: [
      { name: "label", type: "text", max: 28, required: true }, { name: "value", type: "text", max: 40 },
    ] }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "md", weight: 800, transform: "upper", tracking: "wide" }, { as: "h2" }),
      rep("items", "it", box({ dir: "row", gap: "sm", align: "center" }, [
        box({ w: "auto", h: 14, minH: 14, bg: "$cycle", radius: "xs", pad: "sm" }),
        txt(bind("it.label"), { size: "sm", weight: 600 }, { as: "span" }),
        txt(bind("it.value"), { size: "sm", opacity: 0.7, grow: 1, talign: "right" }, { as: "span", when: { $bind: "it.value" } }),
      ]), { style: { dir: "col", gap: "sm" } }),
    ]),
    sample: { title: "Visible spectrum", items: [
      { label: "Violet", value: "380–450 nm" }, { label: "Blue", value: "450–495 nm" },
      { label: "Green", value: "495–570 nm" }, { label: "Red", value: "620–750 nm" },
    ] },
  },
];
