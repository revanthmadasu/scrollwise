import { Link, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";

/**
 * Guards the admin surface. Logged-out users go to the admin login; logged-in
 * non-admins get an access-denied screen (bouncing them to a login they can't
 * pass would be confusing). The real enforcement is server-side (403).
 */
export function AdminProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  if (!user) return <Navigate to="/admin/login" replace />;
  if (!user.is_admin) return <AdminDenied />;
  return <>{children}</>;
}

function AdminDenied() {
  const { logout } = useAuth();
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="brand big">Admin</h1>
        <p className="tagline">This account doesn't have admin access.</p>
        <div className="page-actions">
          <Link className="primary" to="/admin/login" onClick={logout}>
            Sign in as an admin
          </Link>
          <Link className="switch" to="/">
            Back to the app
          </Link>
        </div>
      </div>
    </div>
  );
}
