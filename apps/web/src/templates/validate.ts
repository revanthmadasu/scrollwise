import type { TemplateInputs, TemplateMeta } from "./types";

export interface InputViolation {
  field: string;
  issue: string;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  // Trim to the last word boundary under the limit, then add an ellipsis.
  const slice = text.slice(0, max - 1);
  const lastSpace = slice.lastIndexOf(" ");
  return (lastSpace > max * 0.6 ? slice.slice(0, lastSpace) : slice).trimEnd() + "…";
}

/**
 * Clamp LLM-supplied inputs to a template's capacity. Returns the safe-to-render
 * inputs plus a list of what was over the limit — so the generator can log/flag
 * a bad fit while the client never renders a broken card.
 */
export function clampInputs(
  meta: TemplateMeta,
  inputs: TemplateInputs,
): { inputs: TemplateInputs; violations: InputViolation[] } {
  const cap = meta.capacity;
  const violations: InputViolation[] = [];
  const out: TemplateInputs = { ...inputs };

  if (out.title.length > cap.maxTitleChars) {
    violations.push({ field: "title", issue: `> ${cap.maxTitleChars} chars` });
    out.title = truncate(out.title, cap.maxTitleChars);
  }

  if (out.subtitle && cap.maxSubtitleChars && out.subtitle.length > cap.maxSubtitleChars) {
    violations.push({ field: "subtitle", issue: `> ${cap.maxSubtitleChars} chars` });
    out.subtitle = truncate(out.subtitle, cap.maxSubtitleChars);
  }

  if (out.body && cap.maxBodyChars && out.body.length > cap.maxBodyChars) {
    violations.push({ field: "body", issue: `> ${cap.maxBodyChars} chars` });
    out.body = truncate(out.body, cap.maxBodyChars);
  }

  if (out.bullets && out.bullets.length > (cap.maxBullets ?? 0)) {
    violations.push({ field: "bullets", issue: `> ${cap.maxBullets ?? 0} items` });
    out.bullets = out.bullets.slice(0, cap.maxBullets ?? 0);
  }

  if (out.stats && out.stats.length > (cap.maxStats ?? 0)) {
    violations.push({ field: "stats", issue: `> ${cap.maxStats ?? 0} items` });
    out.stats = out.stats.slice(0, cap.maxStats ?? 0);
  }

  if (out.images && out.images.length > (cap.maxImages ?? 0)) {
    violations.push({ field: "images", issue: `> ${cap.maxImages ?? 0} images` });
    out.images = out.images.slice(0, cap.maxImages ?? 0);
  }

  if (out.svg && !cap.hasSvgSlot) {
    violations.push({ field: "svg", issue: "template has no SVG slot" });
    out.svg = undefined;
  }

  if (out.lottie && !cap.hasLottieSlot) {
    violations.push({ field: "lottie", issue: "template has no Lottie slot" });
    out.lottie = undefined;
  }

  return { inputs: out, violations };
}
