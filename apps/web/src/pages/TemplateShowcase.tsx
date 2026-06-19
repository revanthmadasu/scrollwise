import { TemplateRenderer } from "../templates/TemplateRenderer";
import { ALL_TEMPLATES } from "../templates/index";
import { ThemeToggle } from "../components/ThemeToggle";
import { SAMPLES } from "../templates/samples";

export function TemplateShowcase() {
  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "32px 16px", display: "flex", flexDirection: "column", gap: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h1 style={{ color: "var(--text)", fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
          Template Showcase
        </h1>
        <ThemeToggle />
      </div>
      {ALL_TEMPLATES.map((doc) => (
        <section key={doc.template_id} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: "var(--muted)", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {doc.name}
            </span>
            <span style={{ background: "var(--surface-2)", color: "var(--text-soft)", fontSize: "0.7rem", padding: "2px 8px", borderRadius: 20 }}>
              {doc.vibe}
            </span>
          </div>
          <TemplateRenderer
            templateId={doc.template_id}
            inputs={SAMPLES[doc.template_id] ?? { title: doc.name }}
          />
        </section>
      ))}
    </div>
  );
}
