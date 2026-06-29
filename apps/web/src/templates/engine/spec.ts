/**
 * The data-driven template contract.
 *
 * A template is plain data (a `TemplateDoc`) — no React. The engine
 * (`TemplateEngine`) interprets the `layout` node tree, binding values from the
 * post's inputs per the `fields` field-spec. This is the exact shape that lives
 * in the DB (`templates.fields` / `templates.layout` / `templates.palette`);
 * the local `defs/` are just the seed catalog until they're served from the API.
 */

export type Vibe = "energetic" | "calm" | "playful" | "structured";

/** Inputs fed to a template — an open bag validated against the field-spec. */
export type TemplateInputs = Record<string, unknown>;

// --- Field-spec (the input contract) ----------------------------------------

export type FieldType = "text" | "rich" | "number" | "color" | "enum" | "asset" | "list";
export type AssetKind = "svg" | "lottie" | "image";

export interface Field {
  name: string;
  type: FieldType;
  required?: boolean;
  /** chars for text/rich; item count for list; numeric ceiling for number. */
  max?: number;
  /** item count for list; numeric floor for number. */
  min?: number;
  asset?: AssetKind; // when type === "asset"
  values?: string[]; // when type === "enum"
  /** list of objects → sub-fields; list of scalars → a single item descriptor. */
  of?: Field[];
  item?: Field;
  /** human-readable hint, surfaced to the builder UI and the LLM tool schema. */
  label?: string;
}

export type FieldSpec = Field[];

// --- Layout DSL (the node tree) ---------------------------------------------

/** A value is either a literal or a binding into the inputs/scope. */
export interface Binding {
  $bind: string;
}
export type Value<T = string> = T | Binding;
/** A render guard: a field path (string) or an explicit binding. */
export type Guard = string | Binding;

export type PaletteToken = "$accent" | "$bg" | "$surface" | "$text" | "$cycle";
export type StyleScalar = "xs" | "sm" | "md" | "lg" | "xl";
export type FontSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";

/**
 * Whitelisted style tokens. Rich enough to express a distinct layout from data
 * alone (no per-template CSS), but every value is an enum/number mapped through
 * a fixed table in style.ts — nothing freeform reaches the DOM.
 */
export interface StyleSpec {
  /** A CSS class already shipped in index.css (scene textures, animations). */
  preset?: string;

  // layout
  dir?: "row" | "col";
  gap?: StyleScalar;
  pad?: StyleScalar;
  padX?: StyleScalar;
  padY?: StyleScalar;
  radius?: StyleScalar | "full" | "none";
  align?: "start" | "center" | "end" | "stretch" | "baseline";
  justify?: "start" | "center" | "between" | "end" | "around";
  wrap?: boolean;
  grow?: number;
  w?: "full" | "half" | "auto";
  h?: "full" | "auto" | number;
  minH?: number;

  // color
  bg?: PaletteToken | string;
  fg?: PaletteToken | string;
  border?: PaletteToken | string;
  borderWidth?: number;
  /** A single-side colored accent bar (uses $accent unless `border` is set). */
  accentBar?: "left" | "top" | "right" | "bottom";
  opacity?: number;
  shadow?: "sm" | "md" | "lg";

  // typography
  size?: FontSize;
  weight?: 400 | 500 | 600 | 700 | 800 | 900;
  talign?: "left" | "center" | "right";
  transform?: "upper" | "none";
  tracking?: "tight" | "normal" | "wide" | "wider";
  leading?: "tight" | "normal" | "loose";
  italic?: boolean;
  serif?: boolean;
  mono?: boolean;

  // positioning (decorative overlays: ribbons, bars, badges)
  pos?: "relative" | "absolute";
  inset?: { top?: number; right?: number; bottom?: number; left?: number };
  z?: number;

  // media
  fit?: "cover" | "contain";

  /** Set CSS custom properties (e.g. {"--stat-color":"$cycle"}). */
  vars?: Record<string, PaletteToken | string>;
}

interface NodeBase {
  /** Render only when this resolves truthy. */
  when?: Guard;
  /** Render only when this resolves falsy (mutually exclusive branches). */
  unless?: Guard;
  style?: StyleSpec;
}

export interface BoxNode extends NodeBase {
  type: "box";
  /** HTML tag override (div by default) — lets a box be a ul/li/section/etc. */
  as?: "div" | "section" | "header" | "footer" | "article" | "aside" | "ul" | "li" | "span" | "blockquote";
  children?: LayoutNode[];
}
export interface TextNode extends NodeBase {
  type: "text";
  as?: "h1" | "h2" | "h3" | "p" | "span" | "li" | "blockquote";
  value: Value<string>;
}
export interface ImageNode extends NodeBase {
  type: "image";
  src: Value<string>;
  alt?: Value<string>;
}
export interface SvgNode extends NodeBase {
  type: "svg";
  markup: Value<string>;
}
export interface LottieNode extends NodeBase {
  type: "lottie";
  /** A URL string or an inline Lottie JSON object. */
  src: Value<string | Record<string, unknown>>;
  loop?: boolean;
}
export interface DecoNode extends NodeBase {
  type: "deco";
  variant: "glow" | "minimal" | "playful" | "structured";
  seed?: Value<string>;
}
export interface RepeatNode extends NodeBase {
  type: "repeat";
  /** Field path to the array being iterated. */
  over: string;
  /** Scope alias each item is exposed under (e.g. "stat" → {$bind:"stat.value"}). */
  as: string;
  /** Optional wrapper element around the repeated children. */
  wrap?: { as?: BoxNode["as"]; style?: StyleSpec };
  child: LayoutNode;
}

export type LayoutNode =
  | BoxNode
  | TextNode
  | ImageNode
  | SvgNode
  | LottieNode
  | DecoNode
  | RepeatNode;

// --- Palette + the template document ----------------------------------------

export interface Palette {
  accent: string;
  bg: string;
  surface: string;
  text: string;
}
export interface ThemePalette {
  light: Palette;
  dark: Palette;
}

export interface TemplateDoc {
  template_id: string;
  name: string;
  version: number;
  /** Node-vocabulary version the renderer must support. */
  engine: number;
  status?: string;
  vibe: Vibe;
  description: string;
  content_types: string[];
  /** Organizational labels for the showcase (scene/age/length/theme). NOT a
   * selection contract — the generator selects on vibe + content_types only. */
  tags?: string[];
  palette: ThemePalette;
  /** Cycle palette for the `$cycle` token (per-item accent in repeats). */
  accents?: string[];
  fields: FieldSpec;
  layout: LayoutNode;
  /** Example inputs that satisfy `fields`, used by the showcase/builder. */
  sample?: TemplateInputs;
}

/** Node-vocabulary version this renderer implements. */
export const ENGINE_VERSION = 1;
