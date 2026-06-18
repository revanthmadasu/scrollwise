import type { TemplateInputs } from "./types";
import { compoundingLottie } from "./assets/compoundingLottie";

/** Sample inputs used to preview each template, keyed by template id. */
export const SAMPLES: Record<string, TemplateInputs> = {
  "glow-pulse": {
    title: "Why Black Holes Bend Time",
    subtitle: "General relativity's wildest prediction",
    body: "Mass curves spacetime so severely near a black hole that time itself slows. A clock at the event horizon would appear frozen to a distant observer.",
    bullets: [
      "Time dilation is measurable even on Earth (GPS satellites)",
      "At the event horizon, time stops relative to outside",
      "Hawking radiation slowly evaporates black holes over eons",
    ],
  },
  "minimal-scroll": {
    title: "The Stoic Practice of Negative Visualization",
    subtitle: "Premeditatio Malorum — imagining the worst to appreciate the present",
    body: "Stoic philosophers deliberately pictured losing what they valued most — health, relationships, freedom — not to dwell in despair, but to dissolve the numbness of familiarity. When you imagine your morning coffee as if it might be your last, it tastes different. Seneca called this the antidote to entitlement. The practice interrupts hedonic adaptation: the psychological tendency to take good things for granted the moment they become routine. Five minutes of negative visualization can restore gratitude that months of abundance eroded.",
    bullets: [
      "Seneca wrote letters on this practice daily",
      "Modern psychology calls it 'prospective hindsight'",
      "Works best first thing in the morning",
    ],
  },
  "lottie-hero": {
    title: "Compounding: The Eighth Wonder",
    subtitle: "Why starting at 22 beats starting at 32",
    body: "10 years of compounding at 8% doubles your money. 30 years turns $10k into $100k. Time is the variable nobody sells you.",
    bullets: [
      "$1 at 25 → $21 at 65 (at 8%)",
      "Warren Buffett earned 97% of his wealth after 65",
    ],
    lottie: { id: "compounding-growth", src: compoundingLottie },
  },
  "infographic-card": {
    title: "The Human Brain at a Glance",
    subtitle: "Key numbers every learner should know",
    stats: [
      { label: "Neurons", value: "86B" },
      { label: "Synapses", value: "100T" },
      { label: "Processing speed", value: "120", unit: "m/s" },
      { label: "Memory capacity", value: "2.5", unit: "PB" },
      { label: "Energy use", value: "20", unit: "W" },
    ],
    body: "Your brain runs on less power than a dim light bulb yet outperforms any computer at pattern recognition and abstraction.",
  },
};

/**
 * Strip heavy / binary asset fields (Lottie JSON, raw SVG, image blobs) so the
 * persisted `sample_inputs` stays a small, text-only record of the preview.
 */
export function textOnlySample(inputs: TemplateInputs): Record<string, unknown> {
  const { lottie, svg, images, ...rest } = inputs;
  void lottie;
  void svg;
  void images;
  return rest;
}
