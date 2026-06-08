import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand" onClick={() => navigate("/")}>
          Scroll<span>Wise</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Feed</NavLink>
          <NavLink to="/discover">Discover</NavLink>
          <NavLink to="/interests">Interests</NavLink>
          <NavLink to="/progress">Progress</NavLink>
        </nav>
        <div className="user-menu">
          <span className="muted">{user?.display_name || user?.email}</span>
          <button className="ghost" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
