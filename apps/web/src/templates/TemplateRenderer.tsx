import { TEMPLATE_REGISTRY } from "./index";
import type { TemplateInputs } from "./types";
import { clampInputs } from "./validate";

interface Props {
  templateId: string;
  inputs: TemplateInputs;
  className?: string;
}

/** Looks up the template by id and renders it. Falls back to a plain text card if unknown. */
export function TemplateRenderer({ templateId, inputs, className }: Props) {
  const entry = TEMPLATE_REGISTRY[templateId];
  if (!entry) {
    return (
      <div className={`tmpl-fallback ${className ?? ""}`}>
        <h2>{inputs.title}</h2>
        {inputs.body && <p>{inputs.body}</p>}
      </div>
    );
  }
  const { Component, meta } = entry;
  // Defensive clamp: never let an over-long payload break the card layout.
  const { inputs: safe } = clampInputs(meta, inputs);
  return <Component inputs={safe} className={className} />;
}
