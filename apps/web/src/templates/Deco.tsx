/**
 * FNV-1a hash → stable 32-bit seed from any string (e.g. the post title).
 * Uses the whole string, so titles sharing a prefix don't collide.
 */
function hashString(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/**
 * Lightweight seeded pseudo-random so decorations are stable per post
 * (same seed → same layout every render, no hydration flash).
 */
function seededRand(seed: number) {
  // Guard against a non-finite seed (empty string, NaN) so r() never returns NaN.
  let s = Number.isFinite(seed) && seed !== 0 ? seed >>> 0 : 0x9e3779b9;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

export type DecoVariant = "glow" | "minimal" | "playful" | "structured";

interface DecoProps {
  variant: DecoVariant;
  /** Any stable string (the post title). Hashed to seed the layout. */
  seedKey?: string;
  accent: string;
}

/**
 * Purely decorative SVG layer — floating circles, boxes, dots, rings.
 * Placed as position:absolute behind content; pointer-events: none.
 */
export function Deco({ variant, seedKey = "scrollwise", accent }: DecoProps) {
  const r = seededRand(hashString(seedKey));

  if (variant === "glow") {
    return (
      <svg
        aria-hidden="true"
        className="deco-layer"
        viewBox="0 0 400 280"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Large blurred circle top-right */}
        <circle cx={r() * 80 + 320} cy={r() * 60 + 10} r={80} fill={accent} opacity={0.08} />
        {/* Medium ring */}
        <circle cx={r() * 60 + 30} cy={r() * 60 + 180} r={50} fill="none" stroke={accent} strokeWidth={1.5} opacity={0.18} />
        {/* Small solid circles */}
        {[...Array(6)].map((_, i) => (
          <circle key={i} cx={r() * 380 + 10} cy={r() * 260 + 10} r={r() * 4 + 2} fill={accent} opacity={r() * 0.25 + 0.1} />
        ))}
        {/* Thin rectangles */}
        <rect x={r() * 300 + 20} y={r() * 200 + 20} width={r() * 40 + 20} height={2} rx={1} fill={accent} opacity={0.2} transform={`rotate(${r() * 30 - 15}, 200, 140)`} />
        <rect x={r() * 300 + 20} y={r() * 200 + 20} width={2} height={r() * 40 + 20} rx={1} fill={accent} opacity={0.15} />
        {/* Corner square outline */}
        <rect x={340} y={220} width={36} height={36} rx={4} fill="none" stroke={accent} strokeWidth={1} opacity={0.2} />
      </svg>
    );
  }

  if (variant === "minimal") {
    return (
      <svg
        aria-hidden="true"
        className="deco-layer"
        viewBox="0 0 400 400"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Subtle grid dots */}
        {[...Array(12)].map((_, i) => (
          <circle key={i} cx={(i % 4) * 110 + 30} cy={Math.floor(i / 4) * 120 + 60} r={1.5} fill={accent} opacity={0.2} />
        ))}
        {/* Large thin ring far corner */}
        <circle cx={370} cy={370} r={90} fill="none" stroke={accent} strokeWidth={0.8} opacity={0.12} />
        {/* Horizontal rule accents */}
        <line x1={0} y1={r() * 300 + 50} x2={r() * 80 + 20} y2={r() * 300 + 50} stroke={accent} strokeWidth={1} opacity={0.25} />
        {/* Small rotated square */}
        <rect x={r() * 300 + 30} y={r() * 320 + 30} width={14} height={14} rx={2} fill="none" stroke={accent} strokeWidth={1} opacity={0.2} transform={`rotate(45, ${r() * 300 + 37}, ${r() * 320 + 37})`} />
      </svg>
    );
  }

  if (variant === "playful") {
    return (
      <svg
        aria-hidden="true"
        className="deco-layer"
        viewBox="0 0 400 300"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Scattered filled circles — different sizes, fun */}
        {[...Array(8)].map((_, i) => (
          <circle key={i} cx={r() * 380 + 10} cy={r() * 280 + 10} r={r() * 12 + 4} fill={accent} opacity={r() * 0.2 + 0.05} />
        ))}
        {/* Star-like cross */}
        <line x1={r() * 300 + 50} y1={60} x2={r() * 300 + 70} y2={60} stroke={accent} strokeWidth={2} opacity={0.3} strokeLinecap="round" />
        <line x1={r() * 300 + 60} y1={50} x2={r() * 300 + 60} y2={70} stroke={accent} strokeWidth={2} opacity={0.3} strokeLinecap="round" />
        {/* Rounded squares */}
        {[...Array(3)].map((_, i) => (
          <rect key={i} x={r() * 340 + 20} y={r() * 240 + 20} width={r() * 18 + 8} height={r() * 18 + 8} rx={4} fill={accent} opacity={r() * 0.15 + 0.05} transform={`rotate(${r() * 40 - 20}, 200, 150)`} />
        ))}
        {/* Big faint ring */}
        <circle cx={r() * 100 + 20} cy={r() * 100 + 200} r={70} fill="none" stroke={accent} strokeWidth={1} opacity={0.1} strokeDasharray="4 6" />
      </svg>
    );
  }

  // structured
  return (
    <svg
      aria-hidden="true"
      className="deco-layer"
      viewBox="0 0 400 400"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Grid lines — blueprint feel */}
      {[1, 2, 3].map((i) => (
        <line key={`h${i}`} x1={0} y1={i * 100} x2={400} y2={i * 100} stroke={accent} strokeWidth={0.5} opacity={0.08} />
      ))}
      {[1, 2, 3].map((i) => (
        <line key={`v${i}`} x1={i * 100} y1={0} x2={i * 100} y2={400} stroke={accent} strokeWidth={0.5} opacity={0.08} />
      ))}
      {/* Corner brackets */}
      <path d="M10,30 L10,10 L30,10" fill="none" stroke={accent} strokeWidth={1.5} opacity={0.3} strokeLinecap="round" />
      <path d="M370,30 L370,10 L350,10" fill="none" stroke={accent} strokeWidth={1.5} opacity={0.3} strokeLinecap="round" />
      <path d="M10,370 L10,390 L30,390" fill="none" stroke={accent} strokeWidth={1.5} opacity={0.3} strokeLinecap="round" />
      {/* Data-point dots */}
      {[...Array(5)].map((_, i) => (
        <circle key={i} cx={r() * 360 + 20} cy={r() * 360 + 20} r={3} fill={accent} opacity={0.25} />
      ))}
      {/* Small solid square accent */}
      <rect x={r() * 320 + 40} y={r() * 320 + 40} width={10} height={10} fill={accent} opacity={0.15} />
    </svg>
  );
}
