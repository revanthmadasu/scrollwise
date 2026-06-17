import type { TemplateProps, TemplateMeta } from "./types";
import { Deco } from "./Deco";
import { useTemplatePalette } from "./useTemplatePalette";

export const meta: TemplateMeta = {
  id: "minimal-scroll",
  name: "MinimalScroll",
  vibe: "calm",
  compatibleContentTypes: ["text", "carousel"],
  capacity: {
    maxTitleChars: 80,
    maxSubtitleChars: 120,
    maxBodyChars: 800,
    maxBullets: 6,
    maxImages: 2,
    hasSvgSlot: true,
    hasLottieSlot: false,
  },
  requiredInputs: ["title", "body"],
  optionalInputs: ["subtitle", "bullets", "images", "svg", "accentColor"],
  palette: {
    dark: { accent: "#6ee7b7", bg: "#0c0f0e", surface: "#111714", text: "#e2f5ee" },
    light: { accent: "#059669", bg: "#f5faf8", surface: "#ecfdf5", text: "#064e3b" },
  },
  description: "Clean serif layout for long-form reading. Calm, intellectual — highest body capacity.",
};

export function MinimalScroll({ inputs, className }: TemplateProps) {
  const { title, subtitle, body, bullets, images, svg, accentColor } = inputs;
  const { accent, style } = useTemplatePalette(meta, accentColor);

  return (
    <div className={`tmpl-minimal-scroll ${className ?? ""}`} style={style}>
      <div className="ms-accent-line" />
      <Deco variant="minimal" accent={accent} seedKey={title} />

      <header className="ms-header">
        <h2 className="ms-title">{title}</h2>
        {subtitle && <p className="ms-subtitle">{subtitle}</p>}
      </header>

      {svg && (
        <div
          className="ms-svg-slot"
          dangerouslySetInnerHTML={{ __html: svg.markup }}
        />
      )}

      {images && images.length > 0 && (
        <div className="ms-images">
          {images.map((img) => (
            <img key={img.id} src={img.url} alt={img.alt ?? ""} className="ms-image" />
          ))}
        </div>
      )}

      {body && <p className="ms-body">{body}</p>}

      {bullets && bullets.length > 0 && (
        <ul className="ms-bullets">
          {bullets.map((b, i) => (
            <li key={i} className="ms-bullet">{b}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
