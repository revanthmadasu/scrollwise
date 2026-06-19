export { GlowPulse, meta as glowPulseMeta } from "./GlowPulse";
export { MinimalScroll, meta as minimalScrollMeta } from "./MinimalScroll";
export { LottieHero, meta as lottieHeroMeta } from "./LottieHero";
export { InfographicCard, meta as infographicCardMeta } from "./InfographicCard";
export type { TemplateInputs, TemplateMeta, TemplateProps, TemplateCapacity, InputField, Palette, ThemePalette, Vibe, ContentTypeCompat, SvgAsset, LottieAsset, ImageAsset } from "./types";
export { clampInputs } from "./validate";
export type { InputViolation } from "./validate";

import { GlowPulse, meta as glowPulseMeta } from "./GlowPulse";
import { MinimalScroll, meta as minimalScrollMeta } from "./MinimalScroll";
import { LottieHero, meta as lottieHeroMeta } from "./LottieHero";
import { InfographicCard, meta as infographicCardMeta } from "./InfographicCard";
import type { TemplateMeta, TemplateProps } from "./types";

export type TemplateComponent = (props: TemplateProps) => JSX.Element;

export const TEMPLATE_REGISTRY: Record<string, { meta: TemplateMeta; Component: TemplateComponent }> = {
  [glowPulseMeta.id]: { meta: glowPulseMeta, Component: GlowPulse },
  [minimalScrollMeta.id]: { meta: minimalScrollMeta, Component: MinimalScroll },
  [lottieHeroMeta.id]: { meta: lottieHeroMeta, Component: LottieHero },
  [infographicCardMeta.id]: { meta: infographicCardMeta, Component: InfographicCard },
};

export const ALL_TEMPLATES = Object.values(TEMPLATE_REGISTRY).map((e) => e.meta);
