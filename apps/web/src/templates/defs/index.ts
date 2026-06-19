/**
 * The seed template catalog. These are plain TemplateDoc data — the exact shape
 * stored in the DB (`templates.fields` / `.layout` / `.palette`). Until the API
 * serves them, the client reads them from here; swapping to a fetched list is a
 * one-line change in TemplateRenderer/showcase.
 */
import type { TemplateDoc } from "../engine/spec";
import { glowPulse } from "./glowPulse";
import { minimalScroll } from "./minimalScroll";
import { lottieHero } from "./lottieHero";
import { infographicCard } from "./infographicCard";

export const TEMPLATE_DOCS: TemplateDoc[] = [glowPulse, minimalScroll, lottieHero, infographicCard];

export const TEMPLATE_BY_ID: Record<string, TemplateDoc> = Object.fromEntries(
  TEMPLATE_DOCS.map((d) => [d.template_id, d]),
);
