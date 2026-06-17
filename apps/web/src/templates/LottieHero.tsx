import Lottie from "lottie-react";
import type { TemplateProps, TemplateMeta } from "./types";
import { Deco } from "./Deco";
import { useTemplatePalette } from "./useTemplatePalette";

export const meta: TemplateMeta = {
  id: "lottie-hero",
  name: "LottieHero",
  vibe: "playful",
  compatibleContentTypes: ["text", "image_post"],
  capacity: {
    maxTitleChars: 60,
    maxSubtitleChars: 100,
    maxBodyChars: 240,
    maxBullets: 3,
    maxImages: 0,
    hasSvgSlot: false,
    hasLottieSlot: true,
  },
  requiredInputs: ["title", "lottie"],
  optionalInputs: ["subtitle", "body", "bullets", "accentColor"],
  palette: {
    dark: { accent: "#fbbf24", bg: "#0f0d00", surface: "#1a1700", text: "#fef9e7" },
    light: { accent: "#d97706", bg: "#fffbeb", surface: "#fef3c7", text: "#78350f" },
  },
  description: "Full-bleed Lottie animation as hero. Playful and dynamic — short supporting text only.",
};

export function LottieHero({ inputs, className }: TemplateProps) {
  const { title, subtitle, body, bullets, lottie, accentColor } = inputs;
  const { accent, style } = useTemplatePalette(meta, accentColor);

  return (
    <div className={`tmpl-lottie-hero ${className ?? ""}`} style={style}>
      {lottie ? (
        <div className="lh-lottie-wrap">
          <Lottie
            animationData={typeof lottie.src === "string" ? undefined : lottie.src}
            loop
            className="lh-lottie"
          />
        </div>
      ) : (
        <div className="lh-lottie-placeholder" />
      )}

      <div className="lh-content">
        <Deco variant="playful" accent={accent} seedKey={title} />
        <h2 className="lh-title">{title}</h2>
        {subtitle && <p className="lh-subtitle">{subtitle}</p>}
        {body && <p className="lh-body">{body}</p>}
        {bullets && bullets.length > 0 && (
          <ul className="lh-bullets">
            {bullets.map((b, i) => (
              <li key={i} className="lh-bullet">
                <span className="lh-dot" style={{ background: accent }} />
                {b}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
