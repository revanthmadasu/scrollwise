import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { ThemeToggle } from "../components/ThemeToggle";

/** Bucket a raw waitlist position into a friendly "top N" tier so we never
 * reveal the exact count. Falls back to the widest tier for large positions. */
function positionTier(position: number): string {
  for (const tier of [15, 30, 50, 100, 250, 500, 1000]) {
    if (position <= tier) return `top ${tier}`;
  }
  return "list";
}

const PERKS = [
  {
    emoji: "🧠",
    title: "Learn while you scroll",
    body: "A feed built for curiosity — every swipe teaches you something real instead of wasting your time.",
  },
  {
    emoji: "🎯",
    title: "Personalised depth",
    body: "Pick your level: quick summaries, standard reads, or deep dives. The app remembers and adapts.",
  },
  {
    emoji: "✅",
    title: "Tests that actually help",
    body: "Short quizzes reinforce what you've learned. Fail one? The feed re-serves the material so nothing slips through.",
  },
];

export function WaitlistPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const join = useMutation({
    mutationFn: () => api.joinWaitlist(email, name),
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Something went wrong — try again.");
    },
  });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    join.mutate();
  }

  const done = join.isSuccess;
  const result = join.data;

  return (
    <div className="waitlist-page">
      {/* minimal top bar */}
      <header className="waitlist-bar">
        <div className="brand">
          Scroll<span>Wise</span>
        </div>
        <div className="waitlist-bar-right">
          <ThemeToggle />
          <Link to="/login" className="ghost waitlist-signin">Sign in</Link>
        </div>
      </header>

      <main className="waitlist-main">
        {/* hero */}
        <section className="waitlist-hero">
          <div className="waitlist-badge">Coming soon</div>
          <h1 className="waitlist-headline">
            The feed that makes you<br />
            <span className="waitlist-highlight">smarter, not dumber</span>
          </h1>
          <p className="waitlist-sub">
            ScrollWise is a learning app built to replace doomscrolling — a
            personalised feed of bite-size lessons on topics you actually care
            about, with built-in tests so the knowledge sticks.
          </p>
        </section>

        {/* sign-up card */}
        <div className="waitlist-card">
          {done ? (
            <div className="waitlist-success">
              <div className="waitlist-success-icon">🎉</div>
              {result?.joined ? (
                <>
                  <h2>You're in the {positionTier(result.position)}!</h2>
                  <p className="muted">
                    We'll email <strong>{email}</strong> when early access opens.
                    Tell a friend — the more the merrier.
                  </p>
                </>
              ) : (
                <>
                  <h2>You're already on the list!</h2>
                  <p className="muted">
                    We already have <strong>{email}</strong> saved. We'll be in touch soon.
                  </p>
                </>
              )}
              <a
                className="primary waitlist-share"
                href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(
                  "Just joined the ScrollWise waitlist — a learning feed that actually makes you smarter 🧠 scrollwise.net/waitlist"
                )}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Share on X / Twitter
              </a>
            </div>
          ) : (
            <>
              <h2 className="waitlist-card-title">Get early access</h2>
              <p className="muted waitlist-card-sub">
                Join the waitlist — we're rolling out invites in batches.
              </p>
              <form className="waitlist-form" onSubmit={onSubmit}>
                <input
                  placeholder="Your name (optional)"
                  value={name}
                  maxLength={80}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                />
                <input
                  type="email"
                  placeholder="Your email"
                  value={email}
                  required
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
                {error && <div className="error">{error}</div>}
                <button className="primary" disabled={join.isPending}>
                  {join.isPending ? "Joining…" : "Join the waitlist"}
                </button>
              </form>
              <p className="waitlist-login-hint muted">
                Curious already? <Link to="/login">Explore the prototype →</Link>
              </p>
            </>
          )}
        </div>

        {/* value props */}
        <section className="waitlist-perks">
          {PERKS.map((p) => (
            <div key={p.title} className="waitlist-perk">
              <div className="waitlist-perk-emoji">{p.emoji}</div>
              <div>
                <div className="waitlist-perk-title">{p.title}</div>
                <div className="waitlist-perk-body muted">{p.body}</div>
              </div>
            </div>
          ))}
        </section>
      </main>

      <footer className="waitlist-footer">
        <span className="muted">© 2026 ScrollWise</span>
        <Link to="/login" className="muted">Sign in</Link>
      </footer>
    </div>
  );
}
