/** Shared types for the ScrollWise template system. */

export type Vibe = "energetic" | "calm" | "playful" | "structured";

export type ContentTypeCompat = "text" | "image_post" | "carousel" | "video";

/** A named SVG passed into a template's svg slot. */
export interface SvgAsset {
  id: string;
  /** Raw SVG markup string. */
  markup: string;
}

/** A Lottie animation. Either a URL or a pre-loaded JSON object. */
export interface LottieAsset {
  id: string;
  /** Remote URL to a Lottie JSON file, OR an inline animation data object. */
  src: string | Record<string, unknown>;
}

/** An image asset. */
export interface ImageAsset {
  id: string;
  url: string;
  alt?: string;
}

/**
 * TemplateInputs — what a caller must supply to render any template.
 * Each template defines which fields are required vs optional.
 */
export interface TemplateInputs {
  // --- Content ---
  title: string;
  /** Short subtitle or hook line. Max ~80 chars. */
  subtitle?: string;
  /** Main body text. Max length varies per template (see meta.capacity). */
  body?: string;
  /** Bullet points / key facts. Max count varies per template. */
  bullets?: string[];
  /** Keyed stats for structured layouts: { label, value, unit? }[] */
  stats?: Array<{ label: string; value: string; unit?: string }>;

  // --- Visual ---
  /** Accent color override (CSS hex/hsl). Falls back to template default. */
  accentColor?: string;
  /** Images to display. Max count varies per template. */
  images?: ImageAsset[];
  /** SVG asset for the designated SVG slot. */
  svg?: SvgAsset;
  /** Lottie animation for the designated animation slot. */
  lottie?: LottieAsset;
}

/** Capacity constraints — what a template can accept. */
export interface TemplateCapacity {
  maxTitleChars: number;
  maxSubtitleChars?: number;
  maxBodyChars?: number;
  maxBullets?: number;
  maxStats?: number;
  maxImages?: number;
  hasSvgSlot: boolean;
  hasLottieSlot: boolean;
}

/** Which content fields a template needs. Lets a selector/LLM know what to fill. */
export type InputField = keyof TemplateInputs;

/** A single resolved color set. */
export interface Palette {
  accent: string;
  bg: string;
  surface: string;
  text: string;
}

/** A template's palette in both app theme modes. */
export interface ThemePalette {
  light: Palette;
  dark: Palette;
}

/** Static metadata exported by every template. */
export interface TemplateMeta {
  id: string;
  name: string;
  vibe: Vibe;
  compatibleContentTypes: ContentTypeCompat[];
  capacity: TemplateCapacity;
  /** Fields the template must receive to render meaningfully. */
  requiredInputs: InputField[];
  /** Fields the template will use if present, but can render without. */
  optionalInputs: InputField[];
  /**
   * Palette per app theme mode. The template picks light/dark from the app's
   * resolved theme; `accent` is overridable per-post via inputs.accentColor.
   */
  palette: ThemePalette;
  /** Human-readable description of the template's aesthetic. */
  description: string;
}

/** Props every template component receives. */
export interface TemplateProps {
  inputs: TemplateInputs;
  /** Optional className forwarded to the root element. */
  className?: string;
}
