export * from "./engine/spec";
export { TemplateEngine } from "./engine/TemplateEngine";
export { validateInputs } from "./engine/validate";
export type { InputViolation } from "./engine/validate";
export { TemplateRenderer } from "./TemplateRenderer";
export { TEMPLATE_DOCS, TEMPLATE_BY_ID } from "./defs";

import { TEMPLATE_DOCS } from "./defs";

/** All seed template docs (alias kept for existing callers). */
export const ALL_TEMPLATES = TEMPLATE_DOCS;
