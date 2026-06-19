import type { TemplateProps, TemplateMeta } from "./types";
import { Deco } from "./Deco";
import { useTemplatePalette } from "./useTemplatePalette";

export const meta: TemplateMeta = {
  id: "glow-pulse",
  name: "GlowPulse",
  vibe: "energetic",
  compatibleContentTypes: ["text", "image_post"],
  capacity: {
    maxTitleChars: 60,
    maxSubtitleChars: 100,
    maxBodyChars: 280,
    maxBullets: 4,
    maxImages: 1,
    hasSvgSlot: false,
    hasLottieSlot: false,
  },
  requiredInputs: ["title"],
  optionalInputs: ["subtitle", "body", "bullets", "images", "accentColor"],
  palette: {
    dark: { accent: "#a855f7", bg: "#0a0a0f", surface: "#13101f", text: "#f0e6ff" },
    light: { accent: "#7c3aed", bg: "#faf5ff", surface: "#f3e8ff", text: "#2e1065" },
  },
  description: "Neon glow border with pulsing accent — high energy, short punchy content.",
};

export function GlowPulse({ inputs, className }: TemplateProps) {
  const { title, subtitle, body, bullets, images, accentColor } = inputs;
  const { accent, style } = useTemplatePalette(meta, accentColor);

  return (
    <div className={`tmpl-glow-pulse ${className ?? ""}`} style={style}>
      <div className="gp-glow-ring" />
      <Deco variant="glow" accent={accent} seedKey={title} />

      {images?.[0] && (
        <div className="gp-image-wrap">
          <img src={images[0].url} alt={images[0].alt ?? ""} className="gp-image" />
          <div className="gp-image-overlay" />
        </div>
      )}

      <div className="gp-content">
        <h2 className="gp-title">{title}</h2>
        {subtitle && <p className="gp-subtitle">{subtitle}</p>}
        {body && <p className="gp-body">{body}</p>}
        {bullets && bullets.length > 0 && (
          <ul className="gp-bullets">
            {bullets.map((b, i) => (
              <li key={i} className="gp-bullet">
                <span className="gp-bullet-dot" />
                {b}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="gp-pulse-bar" />
    </div>
  );
}
