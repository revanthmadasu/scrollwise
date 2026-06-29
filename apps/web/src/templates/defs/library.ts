/**
 * The expanded template library — distinct, hand-authored layouts (not palette
 * variants), expressed as pure data via the engine's style tokens + a few shared
 * scene presets. `tags` are organizational only (scene / age / length / theme);
 * selection still keys off vibe + content_types.
 */
import type { TemplateDoc } from "../engine/spec";
import { F, PALETTES, SAMPLE_IMG, SAMPLE_IMG_BIO, SAMPLE_TEXT, bind, box, deco, img, rep, txt } from "./_kit";

const S = SAMPLE_TEXT;
const IMG_PHYS = SAMPLE_IMG;
const IMG_BIO = SAMPLE_IMG_BIO;

export const LIBRARY: TemplateDoc[] = [
  // 1 — full-bleed photo on top, caption below
  {
    template_id: "photo-hero", name: "PhotoHero", version: 1, engine: 1, vibe: "energetic",
    description: "Edge-to-edge image with a caption block beneath — strong visual lead.",
    content_types: ["image_post"], tags: ["image", "energetic", "medium", "adult"],
    palette: PALETTES.ocean,
    fields: [F.title(60), F.subtitle(90), F.body(180), F.image(), F.accent()],
    layout: box({ preset: "te-card", dir: "col", radius: "lg", bg: "$bg", fg: "$text" }, [
      img(bind("images.0.url"), { w: "full", h: 180, fit: "cover" }, { when: { $bind: "images.0" }, alt: bind("images.0.alt") }),
      box({ dir: "col", gap: "sm", pad: "lg" }, [
        txt(bind("title"), { size: "2xl", weight: 800, leading: "tight" }, { as: "h2" }),
        txt(bind("subtitle"), { size: "md", fg: "$accent", weight: 600 }, { as: "p", when: "subtitle" }),
        txt(bind("body"), { size: "sm", leading: "normal", opacity: 0.85 }, { as: "p", when: "body" }),
      ]),
    ]),
    sample: { title: S.title, subtitle: S.subtitle, body: S.short, images: [{ url: IMG_PHYS, alt: "scattering" }] },
  },

  // 2 — one enormous number
  {
    template_id: "big-stat", name: "BigStat", version: 1, engine: 1, vibe: "structured",
    description: "A single dominant figure with a label and one line of context.",
    content_types: ["text", "image_post"], tags: ["stat", "structured", "small", "adult"],
    palette: PALETTES.sky,
    fields: [F.title(40), { name: "value", type: "text", required: true, max: 8 }, { name: "unit", type: "text", max: 8 }, F.body(140), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "sm", pad: "xl", bg: "$bg", fg: "$text", radius: "lg", align: "start" }, [
      txt(bind("title"), { size: "sm", transform: "upper", tracking: "wider", fg: "$accent", weight: 700 }, { as: "p" }),
      box({ dir: "row", align: "baseline", gap: "xs" }, [
        txt(bind("value"), { size: "4xl", weight: 900, leading: "tight" }, { as: "span" }),
        txt(bind("unit"), { size: "xl", weight: 700, fg: "$accent" }, { as: "span", when: "unit" }),
      ]),
      txt(bind("body"), { size: "md", leading: "normal", opacity: 0.8 }, { as: "p", when: "body" }),
    ]),
    sample: { title: "Speed of light", value: "299,792", unit: "km/s", body: "Nothing with mass can reach it — the universe's hard limit." },
  },

  // 3 — editorial pull-quote
  {
    template_id: "pull-quote", name: "PullQuote", version: 1, engine: 1, vibe: "calm",
    description: "Large centered serif quotation with attribution. Editorial and reflective.",
    content_types: ["text"], tags: ["quote", "calm", "medium", "adult", "editorial"],
    palette: PALETTES.ink,
    fields: [{ name: "title", type: "rich", required: true, max: 180 }, F.subtitle(60), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "lg", pad: "xl", bg: "$bg", fg: "$text", radius: "lg", align: "center" }, [
      txt("“", { serif: true, size: "4xl", fg: "$accent", leading: "tight" }, { as: "span" }),
      txt(bind("title"), { serif: true, italic: true, size: "xl", talign: "center", leading: "normal" }, { as: "blockquote" }),
      box({ preset: "te-rule-soft", w: "half", h: 2 }),
      txt(bind("subtitle"), { size: "sm", transform: "upper", tracking: "wide", opacity: 0.7 }, { as: "p", when: "subtitle" }),
    ]),
    sample: { title: "The important thing is not to stop questioning. Curiosity has its own reason for existing.", subtitle: "Albert Einstein" },
  },

  // 4 — left accent rail + body + bullets
  {
    template_id: "side-rail", name: "SideRail", version: 1, engine: 1, vibe: "structured",
    description: "Left accent bar with title, body and key points. Clean and analytical.",
    content_types: ["text"], tags: ["structured", "medium", "adult"],
    palette: PALETTES.slate,
    fields: [F.title(70), F.subtitle(100), F.body(260), F.bullets(4), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", accentBar: "left", borderWidth: 5 }, [
      txt(bind("title"), { size: "xl", weight: 700, leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { size: "sm", fg: "$accent", weight: 600 }, { as: "p", when: "subtitle" }),
      txt(bind("body"), { size: "sm", leading: "normal", opacity: 0.85 }, { as: "p", when: "body" }),
      rep("bullets", "b", box({ dir: "row", gap: "sm", align: "start" }, [
        box({ w: "auto", bg: "$accent", radius: "full", h: 6, minH: 6, pad: "xs" }),
        txt(bind("b"), { size: "sm" }, { as: "span" }),
      ]), { style: { dir: "col", gap: "sm" } }, { when: { $bind: "bullets.0" } }),
    ]),
    sample: { title: S.title, subtitle: S.subtitle, body: S.short, bullets: S.bullets },
  },

  // 5 — numbered steps
  {
    template_id: "step-stack", name: "StepStack", version: 1, engine: 1, vibe: "structured",
    description: "Vertical numbered steps — for processes and how-tos.",
    content_types: ["text", "carousel"], tags: ["steps", "structured", "medium", "tween"],
    palette: PALETTES.forest,
    fields: [F.title(60), F.steps(5), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "xl", weight: 800, leading: "tight" }, { as: "h2" }),
      rep("steps", "s", box({ dir: "row", gap: "md", align: "start" }, [
        txt(bind("$n"), { size: "md", weight: 800, fg: "$bg", bg: "$accent", radius: "full", w: "auto", talign: "center", padX: "sm", padY: "xs" }, { as: "span" }),
        box({ dir: "col", gap: "xs", grow: 1 }, [
          txt(bind("s.title"), { size: "md", weight: 700 }, { as: "span" }),
          txt(bind("s.text"), { size: "sm", opacity: 0.8, leading: "normal" }, { as: "span", when: { $bind: "s.text" } }),
        ]),
      ]), { style: { dir: "col", gap: "md" } }),
    ]),
    sample: { title: "How the sky turns blue", steps: S.steps },
  },

  // 6 — versus / comparison
  {
    template_id: "versus", name: "Versus", version: 1, engine: 1, vibe: "playful",
    description: "Two contrasting columns with a central divider — comparisons and debates.",
    content_types: ["text"], tags: ["compare", "playful", "small", "teen"],
    palette: PALETTES.berry, accents: ["#f472b6", "#60a5fa"],
    fields: [F.title(50), { name: "sides", type: "list", required: true, min: 2, max: 2, of: [
      { name: "label", type: "text", required: true, max: 20 }, { name: "value", type: "text", required: true, max: 60 },
    ] }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", align: "center" }, [
      txt(bind("title"), { size: "lg", weight: 800, talign: "center" }, { as: "h2" }),
      box({ dir: "row", gap: "md", align: "stretch", justify: "between", w: "full" }, [
        rep("sides", "side", box({ dir: "col", gap: "sm", grow: 1, pad: "md", radius: "md", align: "center", border: "$cycle", borderWidth: 2, vars: { "--c": "$cycle" } }, [
          txt(bind("side.label"), { size: "sm", transform: "upper", tracking: "wide", weight: 700, fg: "$cycle" }, { as: "span" }),
          txt(bind("side.value"), { size: "sm", talign: "center", leading: "normal" }, { as: "span" }),
        ]), { style: { dir: "row", gap: "md", w: "full", justify: "between" } }),
      ]),
    ]),
    sample: { title: "Waves vs Particles", sides: [{ label: "Wave", value: "Spreads, interferes, diffracts around edges." }, { label: "Particle", value: "Localized, countable, hits one spot at a time." }] },
  },

  // 7 — vertical timeline
  {
    template_id: "timeline-rail", name: "TimelineRail", version: 1, engine: 1, vibe: "structured",
    description: "A vertical timeline of moments — history and sequences.",
    content_types: ["text", "carousel"], tags: ["timeline", "structured", "large", "history", "adult"],
    palette: PALETTES.sand,
    fields: [F.title(60), { name: "events", type: "list", required: true, max: 6, of: [
      { name: "when", type: "text", max: 14, required: true }, { name: "title", type: "text", max: 50, required: true }, { name: "text", type: "text", max: 140 },
    ] }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "xl", weight: 800, serif: true }, { as: "h2" }),
      rep("events", "e", box({ dir: "row", gap: "md", align: "start", accentBar: "left", borderWidth: 2, padX: "md" }, [
        box({ dir: "col", gap: "xs", grow: 1 }, [
          txt(bind("e.when"), { size: "xs", weight: 800, fg: "$accent", tracking: "wide" }, { as: "span" }),
          txt(bind("e.title"), { size: "md", weight: 700 }, { as: "span" }),
          txt(bind("e.text"), { size: "sm", opacity: 0.8, leading: "normal" }, { as: "span", when: { $bind: "e.text" } }),
        ]),
      ]), { style: { dir: "col", gap: "lg" } }),
    ]),
    sample: { title: "A brief history of the atom", events: [
      { when: "400 BC", title: "Democritus", text: "Proposes indivisible 'atomos'." },
      { when: "1803", title: "Dalton", text: "Atoms as tiny solid spheres." },
      { when: "1911", title: "Rutherford", text: "A dense nucleus, mostly empty space." },
      { when: "1926", title: "Schrödinger", text: "Electrons as probability clouds." },
    ] },
  },

  // 8 — horizontal metric band
  {
    template_id: "metric-row", name: "MetricRow", version: 1, engine: 1, vibe: "structured",
    description: "A single row of key metrics with dividers — dashboards and at-a-glance facts.",
    content_types: ["text", "image_post"], tags: ["stat", "structured", "small", "adult"],
    palette: PALETTES.mint, accents: ["#5eead4", "#38bdf8", "#a855f7", "#fb923c"],
    fields: [F.title(50), F.stats(4), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { size: "lg", weight: 700 }, { as: "h2" }),
      box({ dir: "row", gap: "md", wrap: true, justify: "between" }, [
        rep("stats", "stat", box({ dir: "col", gap: "xs", grow: 1, align: "center", padX: "sm" }, [
          txt(bind("stat.value"), { size: "2xl", weight: 900, fg: "$cycle" }, { as: "span" }),
          txt(bind("stat.unit"), { size: "xs", weight: 700, opacity: 0.7 }, { as: "span", when: { $bind: "stat.unit" } }),
          txt(bind("stat.label"), { size: "xs", transform: "upper", tracking: "wide", opacity: 0.7, talign: "center" }, { as: "span" }),
        ]), { style: { dir: "row", gap: "md", justify: "between", w: "full" } }),
      ]),
    ]),
    sample: { title: "Sunlight by the numbers", stats: S.stats },
  },

  // 9 — dictionary entry
  {
    template_id: "dictionary", name: "Dictionary", version: 1, engine: 1, vibe: "calm",
    description: "A term, its pronunciation and definition. Reference and vocabulary.",
    content_types: ["text"], tags: ["definition", "calm", "small", "adult"],
    palette: PALETTES.ink,
    fields: [F.title(40), F.subtitle(40), F.body(200), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "sm", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      txt(bind("title"), { serif: true, size: "2xl", weight: 700 }, { as: "h2" }),
      box({ dir: "row", gap: "sm", align: "baseline" }, [
        txt(bind("subtitle"), { mono: true, size: "sm", opacity: 0.7 }, { as: "span", when: "subtitle" }),
        txt("noun", { italic: true, serif: true, size: "sm", fg: "$accent" }, { as: "span" }),
      ]),
      box({ preset: "te-rule-soft", w: "full", h: 2 }),
      txt(bind("body"), { serif: true, size: "md", leading: "loose" }, { as: "p", when: "body" }),
    ]),
    sample: { title: "Refraction", subtitle: "/rɪˈfrakʃ(ə)n/", body: "The bending of light as it passes from one medium into another of different density — why a straw looks broken in a glass of water." },
  },

  // 10 — flashcard (Q / A)
  {
    template_id: "flashcard", name: "Flashcard", version: 1, engine: 1, vibe: "playful",
    description: "A question with its answer revealed below — study and recall.",
    content_types: ["text"], tags: ["quiz", "playful", "small", "teen"],
    palette: PALETTES.violet,
    fields: [{ name: "title", type: "text", required: true, max: 100 }, F.body(160), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", minH: 160, justify: "center" }, [
      txt("Q", { size: "sm", weight: 900, fg: "$bg", bg: "$accent", radius: "full", w: "auto", padX: "sm", padY: "xs", talign: "center" }, { as: "span" }),
      txt(bind("title"), { size: "xl", weight: 700, leading: "tight" }, { as: "h2" }),
      box({ preset: "te-rule-soft", w: "full", h: 2 }),
      box({ dir: "row", gap: "sm", align: "baseline" }, [
        txt("A", { size: "sm", weight: 900, fg: "$accent" }, { as: "span" }),
        txt(bind("body"), { size: "md", opacity: 0.9, leading: "normal" }, { as: "span", when: "body" }),
      ]),
    ]),
    sample: { title: "Why does the sky turn red at sunset?", body: "Low sun means light crosses more air; the blue fully scatters away and only the long red wavelengths reach you." },
  },

  // 11 — full-bleed gradient cover
  {
    template_id: "gradient-cover", name: "GradientCover", version: 1, engine: 1, vibe: "energetic",
    description: "Bold accent-filled cover with an oversized centered title.",
    content_types: ["text", "image_post"], tags: ["cover", "energetic", "small", "teen"],
    palette: PALETTES.coral,
    fields: [F.title(48), F.subtitle(80), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "xl", bg: "$accent", fg: "#ffffff", radius: "lg", minH: 200, justify: "center", align: "center" }, [
      deco("playful", bind("title")),
      txt(bind("title"), { size: "3xl", weight: 900, talign: "center", leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { size: "md", weight: 600, talign: "center", opacity: 0.9 }, { as: "p", when: "subtitle" }),
    ]),
    sample: { title: "Light is both wave and particle", subtitle: "And that's completely fine" },
  },

  // 12 — chalkboard (classroom)
  {
    template_id: "chalkboard", name: "Chalkboard", version: 1, engine: 1, vibe: "calm",
    description: "Classroom chalkboard with handwritten feel and chalked points.",
    content_types: ["text"], tags: ["scene-classroom", "calm", "medium", "tween"],
    palette: PALETTES.chalk,
    fields: [F.title(60), F.body(200), F.bullets(4), F.accent()],
    layout: box({ preset: "te-card scene-dots", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", border: "$accent", borderWidth: 6 }, [
      txt(bind("title"), { serif: true, italic: true, size: "2xl", weight: 700, talign: "center" }, { as: "h2" }),
      box({ preset: "te-rule-soft", w: "full", h: 2 }),
      txt(bind("body"), { serif: true, size: "md", leading: "loose", opacity: 0.92 }, { as: "p", when: "body" }),
      rep("bullets", "b", box({ dir: "row", gap: "sm", align: "start" }, [
        txt("✓", { fg: "$accent", weight: 800 }, { as: "span" }),
        txt(bind("b"), { serif: true, size: "sm" }, { as: "span" }),
      ]), { style: { dir: "col", gap: "xs" } }, { when: { $bind: "bullets.0" } }),
    ]),
    sample: { title: "Today: Why the Sky Is Blue", body: S.short, bullets: S.bullets },
  },

  // 13 — ruled notebook page (large content)
  {
    template_id: "ruled-note", name: "RuledNote", version: 1, engine: 1, vibe: "calm",
    description: "Lined notebook paper for longer notes. Calm, study-friendly, high capacity.",
    content_types: ["text", "carousel"], tags: ["scene-classroom", "calm", "large", "adult"],
    palette: PALETTES.sand,
    fields: [F.title(70), F.subtitle(110), F.body(800), F.accent()],
    layout: box({ preset: "te-card scene-ruled", dir: "col", gap: "sm", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", accentBar: "left", borderWidth: 4 }, [
      txt(bind("title"), { size: "xl", weight: 800, serif: true }, { as: "h2" }),
      txt(bind("subtitle"), { italic: true, size: "sm", opacity: 0.75 }, { as: "p", when: "subtitle" }),
      txt(bind("body"), { size: "md", leading: "loose" }, { as: "p", when: "body" }),
    ]),
    sample: { title: S.title, subtitle: S.subtitle, body: S.long + " " + S.long },
  },

  // 14 — lab log (science scene)
  {
    template_id: "lab-log", name: "LabLog", version: 1, engine: 1, vibe: "structured",
    description: "Graph-paper lab log with observations. Methodical, science-flavored.",
    content_types: ["text", "image_post"], tags: ["scene-lab", "structured", "medium", "teen"],
    palette: PALETTES.cosmos, accents: ["#818cf8", "#34d399", "#fb923c", "#f472b6"],
    fields: [F.title(60), F.body(180), F.stats(4), F.svg(), F.accent()],
    layout: box({ preset: "te-card scene-grid", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg" }, [
      box({ dir: "row", gap: "sm", align: "center" }, [
        txt("LAB LOG", { mono: true, size: "xs", weight: 700, tracking: "wider", fg: "$bg", bg: "$accent", padX: "sm", padY: "xs", radius: "xs" }, { as: "span" }),
        txt(bind("title"), { size: "lg", weight: 700 }, { as: "h2" }),
      ]),
      txt(bind("body"), { mono: true, size: "sm", leading: "normal", opacity: 0.85 }, { as: "p", when: "body" }),
      box({ dir: "row", gap: "md", wrap: true }, [
        rep("stats", "stat", box({ dir: "col", grow: 1, pad: "sm", radius: "md", bg: "$surface", border: "$cycle" }, [
          txt(bind("stat.value"), { mono: true, size: "lg", weight: 800, fg: "$cycle" }, { as: "span" }),
          txt(bind("stat.label"), { mono: true, size: "xs", opacity: 0.7 }, { as: "span" }),
        ]), { style: { dir: "row", gap: "sm", wrap: true } }, { when: { $bind: "stats.0" } }),
      ]),
    ]),
    sample: { title: "Scattering run #7", body: "Measured intensity vs wavelength across the visible band; blue end dominates as predicted.", stats: S.stats },
  },

  // 15 — cosmos (space scene)
  {
    template_id: "cosmos", name: "Cosmos", version: 1, engine: 1, vibe: "energetic",
    description: "Starfield cover for astronomy and space topics.",
    content_types: ["text", "image_post"], tags: ["scene-space", "energetic", "small", "tween"],
    palette: PALETTES.cosmos,
    fields: [F.title(56), F.subtitle(90), F.accent()],
    layout: box({ preset: "te-card scene-stars", dir: "col", gap: "sm", pad: "xl", bg: "$bg", fg: "$text", radius: "lg", minH: 190, justify: "center", align: "center" }, [
      box({ w: "auto", h: 10, minH: 10, bg: "$accent", radius: "full", pad: "xs", preset: "te-pulse" }),
      txt(bind("title"), { size: "2xl", weight: 800, talign: "center", leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { size: "sm", fg: "$accent", weight: 600, talign: "center", tracking: "wide" }, { as: "p", when: "subtitle" }),
    ]),
    sample: { title: "Why stars twinkle", subtitle: "Turbulent air bends their light on the way down" },
  },

  // 16 — botanical (nature scene)
  {
    template_id: "botanical", name: "Botanical", version: 1, engine: 1, vibe: "calm",
    description: "Soft organic layout for biology and nature. Calm and growing.",
    content_types: ["text"], tags: ["scene-nature", "calm", "medium", "adult", "biology"],
    palette: PALETTES.forest,
    fields: [F.title(64), F.body(240), F.bullets(3), F.image(), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "xl" }, [
      deco("minimal", bind("title")),
      img(bind("images.0.url"), { w: "full", h: 120, fit: "cover", radius: "lg" }, { when: { $bind: "images.0" }, alt: bind("images.0.alt") }),
      txt(bind("title"), { serif: true, size: "xl", weight: 700, leading: "tight" }, { as: "h2" }),
      txt(bind("body"), { size: "sm", leading: "loose", opacity: 0.88 }, { as: "p", when: "body" }),
      rep("bullets", "b", box({ dir: "row", gap: "sm", align: "center" }, [
        txt("❧", { fg: "$accent", size: "md" }, { as: "span" }),
        txt(bind("b"), { size: "sm", italic: true, serif: true }, { as: "span" }),
      ]), { style: { dir: "col", gap: "xs" } }, { when: { $bind: "bullets.0" } }),
    ]),
    sample: { title: "How leaves drink light", body: S.short, bullets: ["Chlorophyll absorbs red + blue", "Reflects green — hence the color", "Builds sugar from air and water"], images: [{ url: IMG_BIO, alt: "cells" }] },
  },

  // 17 — blueprint (city / structural scene)
  {
    template_id: "blueprint", name: "Blueprint", version: 1, engine: 1, vibe: "structured",
    description: "Blueprint grid with bracketed title. Technical and architectural.",
    content_types: ["text", "image_post"], tags: ["scene-city", "structured", "medium", "adult"],
    palette: PALETTES.sky,
    fields: [F.title(60), F.subtitle(90), F.stats(3), F.accent()],
    layout: box({ preset: "te-card scene-blueprint", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "none", border: "$accent", borderWidth: 1 }, [
      deco("structured", bind("title")),
      txt(bind("title"), { mono: true, size: "xl", weight: 700, transform: "upper", tracking: "wide" }, { as: "h2" }),
      txt(bind("subtitle"), { mono: true, size: "sm", fg: "$accent" }, { as: "p", when: "subtitle" }),
      box({ dir: "row", gap: "md", justify: "between", wrap: true }, [
        rep("stats", "stat", box({ dir: "col", gap: "xs", grow: 1, border: "$accent", borderWidth: 1, pad: "sm" }, [
          txt(bind("stat.value"), { mono: true, size: "lg", weight: 800 }, { as: "span" }),
          txt(bind("stat.label"), { mono: true, size: "xs", opacity: 0.7 }, { as: "span" }),
        ]), { style: { dir: "row", gap: "md", w: "full", justify: "between" } }, { when: { $bind: "stats.0" } }),
      ]),
    ]),
    sample: { title: "Suspension bridge", subtitle: "Tension + compression in balance", stats: S.stats },
  },

  // 18 — storybook (kids)
  {
    template_id: "storybook", name: "Storybook", version: 1, engine: 1, vibe: "playful",
    description: "Big, rounded, friendly cover for young learners. Short and bright.",
    content_types: ["text", "image_post"], tags: ["kids", "playful", "small", "scene-nature"],
    palette: PALETTES.candy,
    fields: [F.title(40), F.body(90), F.image(), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "xl", bg: "$surface", fg: "$text", radius: "xl", align: "center", minH: 200, justify: "center" }, [
      deco("playful", bind("title")),
      img(bind("images.0.url"), { w: "full", h: 110, fit: "contain" }, { when: { $bind: "images.0" }, alt: bind("images.0.alt") }),
      txt(bind("title"), { size: "3xl", weight: 900, talign: "center", leading: "tight", fg: "$accent" }, { as: "h2" }),
      txt(bind("body"), { size: "lg", weight: 600, talign: "center", leading: "normal" }, { as: "p", when: "body" }),
    ]),
    sample: { title: "The Sky Is Blue!", body: "Sunlight is sneaky — the air bounces the blue all around us.", images: [{ url: IMG_PHYS, alt: "sky" }] },
  },

  // 19 — neon arcade (teen / energetic)
  {
    template_id: "neon-arcade", name: "NeonArcade", version: 1, engine: 1, vibe: "energetic",
    description: "Dark neon panel with glowing accents — high energy, teen vibe.",
    content_types: ["text", "image_post"], tags: ["teen", "energetic", "small", "scene-space"],
    palette: PALETTES.candy,
    fields: [F.title(50), F.subtitle(80), F.bullets(3), F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "md", pad: "lg", bg: "$bg", fg: "$text", radius: "lg", border: "$accent", borderWidth: 2, shadow: "lg" }, [
      txt(bind("title"), { size: "2xl", weight: 900, transform: "upper", tracking: "wide", fg: "$accent", leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { mono: true, size: "sm", opacity: 0.85 }, { as: "p", when: "subtitle" }),
      rep("bullets", "b", box({ dir: "row", gap: "sm", align: "center", border: "$accent", borderWidth: 1, radius: "md", padX: "sm", padY: "xs" }, [
        txt("▸", { fg: "$accent", weight: 800 }, { as: "span" }),
        txt(bind("b"), { size: "sm", mono: true }, { as: "span" }),
      ]), { style: { dir: "col", gap: "sm" } }, { when: { $bind: "bullets.0" } }),
    ]),
    sample: { title: "Level Up: Optics", subtitle: "> 3 power-ups unlocked", bullets: S.bullets },
  },

  // 20 — ticket stub (novelty)
  {
    template_id: "ticket-stub", name: "TicketStub", version: 1, engine: 1, vibe: "playful",
    description: "An admit-one ticket stub. Playful framing for events and milestones.",
    content_types: ["text"], tags: ["novelty", "playful", "small", "teen"],
    palette: PALETTES.gold,
    fields: [F.title(44), F.subtitle(60), { name: "value", type: "text", max: 12 }, F.accent()],
    layout: box({ preset: "te-card", dir: "col", gap: "sm", pad: "lg", bg: "$surface", fg: "$text", radius: "md", border: "$accent", borderWidth: 2 }, [
      txt("ADMIT ONE", { mono: true, size: "xs", weight: 800, tracking: "wider", fg: "$accent" }, { as: "span" }),
      txt(bind("title"), { size: "xl", weight: 800, leading: "tight" }, { as: "h2" }),
      txt(bind("subtitle"), { mono: true, size: "sm", opacity: 0.8 }, { as: "p", when: "subtitle" }),
      box({ dir: "row", gap: "sm", align: "center", justify: "between", border: "$accent", borderWidth: 0, accentBar: "top" }, [
        txt("NO.", { mono: true, size: "xs", opacity: 0.6 }, { as: "span" }),
        txt(bind("value"), { mono: true, size: "md", weight: 800, fg: "$accent" }, { as: "span", when: "value" }),
      ]),
    ]),
    sample: { title: "Eclipse Viewing", subtitle: "Front-row seat to the cosmos", value: "0420" },
  },
];
