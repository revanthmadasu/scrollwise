import { TEMPLATE_DOCS } from "./defs";
import type { TemplateInputs } from "./engine/spec";

/** Sample inputs used to preview each template, keyed by template id. Sourced
 * from each doc's `sample` so previews track the template definition. */
export const SAMPLES: Record<string, TemplateInputs> = Object.fromEntries(
  TEMPLATE_DOCS.map((d) => [d.template_id, d.sample ?? { title: d.name }]),
);

/**
 * Strip heavy / binary asset fields (Lottie JSON, raw SVG, image blobs) so the
 * persisted `sample_inputs` stays a small, text-only record of the preview.
 */
export function textOnlySample(inputs: TemplateInputs): Record<string, unknown> {
  const { lottie, svg, images, ...rest } = inputs;
  void lottie;
  void svg;
  void images;
  return rest;
}
