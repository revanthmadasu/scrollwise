import { TEMPLATE_BY_ID } from "./defs";
import { TemplateEngine } from "./engine/TemplateEngine";
import type { TemplateInputs } from "./engine/spec";

interface Props {
  templateId: string;
  inputs: TemplateInputs;
  className?: string;
}

/** Looks up the template doc by id and renders it through the engine. Falls back to a plain text card if unknown. */
export function TemplateRenderer({ templateId, inputs, className }: Props) {
  const doc = TEMPLATE_BY_ID[templateId];
  if (!doc) {
    return (
      <div className={`tmpl-fallback ${className ?? ""}`}>
        <h2>{typeof inputs.title === "string" ? inputs.title : ""}</h2>
        {inputs.body != null && <p>{String(inputs.body)}</p>}
      </div>
    );
  }
  return <TemplateEngine doc={doc} inputs={inputs} className={className} />;
}
