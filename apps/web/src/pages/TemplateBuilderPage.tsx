import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { TemplateRecord, TemplateStatus } from "../api/types";
import { ALL_TEMPLATES } from "../templates/index";
import type { TemplateMeta } from "../templates/types";
import { TemplateRenderer } from "../templates/TemplateRenderer";
import { SAMPLES, textOnlySample } from "../templates/samples";

const STATUS_LABEL: Record<TemplateStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  rejected: "Rejected",
  archived: "Archived",
};

/** Map the in-code template meta (camelCase) to the API's submit payload. */
function metaToSubmit(meta: TemplateMeta) {
  const sample = SAMPLES[meta.id];
  return {
    template_id: meta.id,
    name: meta.name,
    vibe: meta.vibe,
    description: meta.description,
    compatible_content_types: meta.compatibleContentTypes,
    capacity: meta.capacity as unknown as Record<string, unknown>,
    required_inputs: meta.requiredInputs,
    optional_inputs: meta.optionalInputs,
    palette: meta.palette as unknown as Record<string, unknown>,
    sample_inputs: sample ? textOnlySample(sample) : null,
  };
}

function capacitySummary(c: TemplateMeta["capacity"]): string {
  const parts: string[] = [`title ≤${c.maxTitleChars}`];
  if (c.maxBodyChars) parts.push(`body ≤${c.maxBodyChars}`);
  if (c.maxBullets) parts.push(`${c.maxBullets} bullets`);
  if (c.maxStats) parts.push(`${c.maxStats} stats`);
  if (c.maxImages) parts.push(`${c.maxImages} img`);
  if (c.hasSvgSlot) parts.push("SVG slot");
  if (c.hasLottieSlot) parts.push("Lottie slot");
  return parts.join(" · ");
}

export function TemplateBuilderPage() {
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["admin-templates"], queryFn: api.listTemplates });

  const byId = new Map<string, TemplateRecord>();
  for (const t of saved.data ?? []) byId.set(t.template_id, t);

  const review = useMutation({
    mutationFn: (vars: { meta: TemplateMeta; status: TemplateStatus; notes: string }) =>
      api.submitTemplate({ ...metaToSubmit(vars.meta), status: vars.status, review_notes: vars.notes || null }),
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
        {ALL_TEMPLATES.map((meta) => (
          <TemplateReviewCard
            key={meta.id}
            meta={meta}
            record={byId.get(meta.id)}
            busy={review.isPending && review.variables?.meta.id === meta.id}
            onReview={(status, notes) => review.mutate({ meta, status, notes })}
          />
        ))}
      </div>
    </div>
  );
}

function TemplateReviewCard({
  meta,
  record,
  busy,
  onReview,
}: {
  meta: TemplateMeta;
  record?: TemplateRecord;
  busy: boolean;
  onReview: (status: TemplateStatus, notes: string) => void;
}) {
  const [notes, setNotes] = useState(record?.review_notes ?? "");
  const status = record?.status ?? null;

  return (
    <section className="tb-card">
      <div className="tb-preview">
        <TemplateRenderer templateId={meta.id} inputs={SAMPLES[meta.id] ?? { title: meta.name }} />
      </div>

      <div className="tb-meta">
        <div className="tb-meta-head">
          <h2>{meta.name}</h2>
          <span className={`tb-status ${status ?? "none"}`}>
            {status ? STATUS_LABEL[status] : "Not reviewed"}
          </span>
        </div>
        <p className="muted tb-desc">{meta.description}</p>

        <dl className="tb-spec">
          <div>
            <dt>Vibe</dt>
            <dd>{meta.vibe}</dd>
          </div>
          <div>
            <dt>Content types</dt>
            <dd>{meta.compatibleContentTypes.join(", ")}</dd>
          </div>
          <div>
            <dt>Required inputs</dt>
            <dd>{meta.requiredInputs.join(", ") || "—"}</dd>
          </div>
          <div>
            <dt>Optional inputs</dt>
            <dd>{meta.optionalInputs.join(", ") || "—"}</dd>
          </div>
          <div className="tb-spec-wide">
            <dt>Capacity</dt>
            <dd>{capacitySummary(meta.capacity)}</dd>
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
