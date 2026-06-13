import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register(email, password, displayName || undefined);
      navigate("/interests"); // new users pick interests first
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="brand big">Scroll<span>Wise</span></h1>
        <p className="tagline">Create your account.</p>
        <div className="prototype-note">
          <span className="prototype-badge">Prototype</span>
          <p>
            You're stepping into an early prototype. We're actively refining things
            behind the scenes to deepen your wisdom-gain experience — expect rough
            edges, and expect them to keep getting better.
          </p>
        </div>
        <form onSubmit={onSubmit} className="auth-form">
          <input placeholder="Display name (optional)" value={displayName}
            maxLength={50}
            onChange={(e) => setDisplayName(e.target.value)} />
          <input type="email" placeholder="Email" value={email} required
            onChange={(e) => setEmail(e.target.value)} />
          <input type="password" placeholder="Password (min 8 chars)" value={password} required
            onChange={(e) => setPassword(e.target.value)} />
          {error && <div className="error">{error}</div>}
          <button className="primary" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        </form>
        <p className="switch">Already have an account? <Link to="/login">Sign in</Link></p>
      </div>
    </div>
  );
}
