import { TemplateRenderer } from "../templates/TemplateRenderer";
import { ALL_TEMPLATES } from "../templates/index";
import { ThemeToggle } from "../components/ThemeToggle";

const SAMPLES: Record<string, import("../templates/types").TemplateInputs> = {
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

export function TemplateShowcase() {
  return (
    <div style={{ maxWidth: 480, margin: "0 auto", padding: "32px 16px", display: "flex", flexDirection: "column", gap: 32 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h1 style={{ color: "var(--text)", fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>
          Template Showcase
        </h1>
        <ThemeToggle />
      </div>
      {ALL_TEMPLATES.map((meta) => (
        <section key={meta.id} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: "var(--muted)", fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {meta.name}
            </span>
            <span style={{ background: "var(--surface-2)", color: "var(--text-soft)", fontSize: "0.7rem", padding: "2px 8px", borderRadius: 20 }}>
              {meta.vibe}
            </span>
          </div>
          <TemplateRenderer
            templateId={meta.id}
            inputs={SAMPLES[meta.id] ?? { title: meta.name }}
          />
        </section>
      ))}
    </div>
  );
}
