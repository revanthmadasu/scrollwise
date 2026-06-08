import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { GoogleButton, googleConfigured } from "../components/GoogleButton";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  const onGoogle = useCallback(
    async (idToken: string) => {
      try {
        await loginWithGoogle(idToken);
        navigate("/");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Google sign-in failed");
      }
    },
    [loginWithGoogle, navigate]
  );

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="brand big">Scroll<span>Wise</span></h1>
        <p className="tagline">Learn by scrolling. The anti-doomscroll feed.</p>

        <form onSubmit={onSubmit} className="auth-form">
          <input type="email" placeholder="Email" value={email} required
            onChange={(e) => setEmail(e.target.value)} />
          <input type="password" placeholder="Password" value={password} required
            onChange={(e) => setPassword(e.target.value)} />
          {error && <div className="error">{error}</div>}
          <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>

        {googleConfigured && (
          <>
            <div className="divider"><span>or</span></div>
            <GoogleButton onCredential={onGoogle} />
          </>
        )}

        <p className="switch">No account? <Link to="/register">Create one</Link></p>
      </div>
    </div>
  );
}
