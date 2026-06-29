import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

export function AdminLoginPage() {
  const { adminLogin, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already signed in as an admin? Skip straight to the builder.
  useEffect(() => {
    if (user?.is_admin) navigate("/admin/templates", { replace: true });
  }, [user, navigate]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await adminLogin(email, password);
      navigate("/admin/templates", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="brand big">
          Scroll<span>Wise</span> <span className="admin-tag">Admin</span>
        </h1>
        <p className="tagline">Sign in to review and approve templates.</p>

        <form onSubmit={onSubmit} className="auth-form">
          <input
            type="email"
            placeholder="Admin email"
            value={email}
            required
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            required
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="error">{error}</div>}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in to admin"}
          </button>
        </form>

        <p className="switch">
          <Link to="/">← Back to the app</Link>
        </p>
      </div>
    </div>
  );
}
