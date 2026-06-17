import type { TemplateProps, TemplateMeta } from "./types";
import { Deco } from "./Deco";
import { useTemplatePalette } from "./useTemplatePalette";

export const meta: TemplateMeta = {
  id: "infographic-card",
  name: "InfographicCard",
  vibe: "structured",
  compatibleContentTypes: ["text", "image_post"],
  capacity: {
    maxTitleChars: 70,
    maxSubtitleChars: 100,
    maxBodyChars: 200,
    maxBullets: 0,
    maxStats: 5,
    maxImages: 1,
    hasSvgSlot: true,
    hasLottieSlot: false,
  },
  requiredInputs: ["title", "stats"],
  optionalInputs: ["subtitle", "body", "images", "svg", "accentColor"],
  palette: {
    dark: { accent: "#38bdf8", bg: "#03080f", surface: "#0a1520", text: "#e0f2fe" },
    light: { accent: "#0284c7", bg: "#f0f9ff", surface: "#e0f2fe", text: "#0c4a6e" },
  },
  description: "Data-first layout with stat blocks and optional SVG diagram. Structured and analytical.",
};

const STAT_ACCENTS = ["#38bdf8", "#818cf8", "#34d399", "#f472b6", "#fb923c"];

export function InfographicCard({ inputs, className }: TemplateProps) {
  const { title, subtitle, body, stats, images, svg, accentColor } = inputs;
  const { accent, style } = useTemplatePalette(meta, accentColor);

  return (
    <div className={`tmpl-infographic-card ${className ?? ""}`} style={style}>
      <Deco variant="structured" accent={accent} seedKey={title} />

      <header className="ic-header">
        {images?.[0] && (
          <img src={images[0].url} alt={images[0].alt ?? ""} className="ic-thumb" />
        )}
        <div>
          <h2 className="ic-title">{title}</h2>
          {subtitle && <p className="ic-subtitle">{subtitle}</p>}
        </div>
      </header>

      {stats && stats.length > 0 && (
        <div className="ic-stats">
          {stats.map((s, i) => (
            <div
              key={i}
              className="ic-stat"
              style={{ "--stat-color": STAT_ACCENTS[i % STAT_ACCENTS.length] } as React.CSSProperties}
            >
              <span className="ic-stat-value">{s.value}</span>
              {s.unit && <span className="ic-stat-unit">{s.unit}</span>}
              <span className="ic-stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {svg && (
        <div
          className="ic-svg-slot"
          dangerouslySetInnerHTML={{ __html: svg.markup }}
        />
      )}

      {body && <p className="ic-body">{body}</p>}
    </div>
  );
}
