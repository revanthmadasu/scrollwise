import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TemplateRecord, TemplateStatus, TemplateSubmit } from "../api/types";
import { ALL_TEMPLATES } from "../templates/index";
import type { TemplateDoc, FieldSpec } from "../templates/engine/spec";
import { TemplateRenderer } from "../templates/TemplateRenderer";
import { SAMPLES, textOnlySample } from "../templates/samples";

const STATUS_LABEL: Record<TemplateStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
  archived: "Archived",
};

/** Map a template doc to the API's submit payload (includes the data-driven
 * render contract: field-spec + layout). required/optional inputs are derived
 * from the field-spec for back-compat with the generator's selection inputs. */
function docToSubmit(doc: TemplateDoc): TemplateSubmit {
  const sample = SAMPLES[doc.template_id];
  return {
    template_id: doc.template_id,
    name: doc.name,
    vibe: doc.vibe,
    description: doc.description,
    compatible_content_types: doc.content_types,
    capacity: {},
    required_inputs: doc.fields.filter((f) => f.required).map((f) => f.name),
    optional_inputs: doc.fields.filter((f) => !f.required).map((f) => f.name),
    palette: doc.palette as unknown as Record<string, unknown>,
    fields: doc.fields as unknown as Record<string, unknown>[],
    layout: doc.layout as unknown as Record<string, unknown>,
    engine: doc.engine,
    sample_inputs: sample ? textOnlySample(sample) : null,
  };
}

/** One-line field-spec summary for the review card. */
function fieldsSummary(fields: FieldSpec): string {
  return fields
    .map((f) => {
      let s = f.name;
      if (f.type === "list") s += `[${f.max ?? "∞"}]`;
      else if (f.type === "asset") s += `(${f.asset})`;
      else if (f.max) s += ` ≤${f.max}`;
      return f.required ? s + "*" : s;
    })
    .join(" · ");
}

export function TemplateBuilderPage() {
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["admin-templates"], queryFn: api.listTemplates });

  const byId = new Map<string, TemplateRecord>();
  for (const t of saved.data ?? []) byId.set(t.template_id, t);

  const review = useMutation({
    mutationFn: (vars: { doc: TemplateDoc; status: TemplateStatus; notes: string }) =>
      api.submitTemplate({ ...docToSubmit(vars.doc), status: vars.status, review_notes: vars.notes || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-templates"] }),
  });

  const approvedCount = (saved.data ?? []).filter((t) => t.status === "approved").length;

  return (
    <div className="page builder">
      <header className="builder-header">
        <h1>Template Builder</h1>
        <p className="muted">
          Review each generated template and approve the ones good enough to ship.
          Approved templates are saved to the database for the content generator to select from.
        </p>
        <p className="builder-count">
          {approvedCount} of {ALL_TEMPLATES.length} templates approved
        </p>
        {saved.isError && (
          <p className="builder-error">Couldn't load saved templates. Is the API running?</p>
        )}
      </header>

      <div className="builder-list">
        {ALL_TEMPLATES.map((doc) => (
          <TemplateReviewCard
            key={doc.template_id}
            doc={doc}
            record={byId.get(doc.template_id)}
            busy={review.isPending && review.variables?.doc.template_id === doc.template_id}
            onReview={(status, notes) => review.mutate({ doc, status, notes })}
          />
        ))}
      </div>
    </div>
  );
}

function TemplateReviewCard({
  doc,
  record,
  busy,
  onReview,
}: {
  doc: TemplateDoc;
  record?: TemplateRecord;
  busy: boolean;
  onReview: (status: TemplateStatus, notes: string) => void;
}) {
  const [notes, setNotes] = useState(record?.review_notes ?? "");
  const status = record?.status ?? null;

  return (
    <section className="tb-card">
      <div className="tb-preview">
        <TemplateRenderer templateId={doc.template_id} inputs={SAMPLES[doc.template_id] ?? { title: doc.name }} />
      </div>

      <div className="tb-meta">
        <div className="tb-meta-head">
          <h2>{doc.name}</h2>
          <span className={`tb-status ${status ?? "none"}`}>
            {status ? STATUS_LABEL[status] : "Not reviewed"}
          </span>
        </div>
        <p className="muted tb-desc">{doc.description}</p>

        <dl className="tb-spec">
          <div>
            <dt>Vibe</dt>
            <dd>{doc.vibe}</dd>
          </div>
          <div>
            <dt>Content types</dt>
            <dd>{doc.content_types.join(", ")}</dd>
          </div>
          <div className="tb-spec-wide">
            <dt>Fields</dt>
            <dd>{fieldsSummary(doc.fields)}</dd>
          </div>
        </dl>

        <textarea
          className="tb-notes"
          placeholder="Review notes (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />

        <div className="tb-actions">
          <button className="primary" disabled={busy} onClick={() => onReview("approved", notes)}>
            {busy ? "Saving…" : status === "approved" ? "Re-approve" : "Approve"}
          </button>
          <button className="ghost" disabled={busy} onClick={() => onReview("rejected", notes)}>
            Reject
          </button>
        </div>

        {record && (
          <p className="tb-version muted">
            v{record.version} · updated {new Date(record.updated_at).toLocaleString()}
          </p>
        )}
      </div>
    </section>
  );
}
