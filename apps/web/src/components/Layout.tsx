import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ChartIcon, CompassIcon, HomeIcon, LogoutIcon, SparklesIcon } from "./icons";
import { ThemeToggle } from "./ThemeToggle";

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
          <NavLink to="/" end><HomeIcon /><span>Feed</span></NavLink>
          <NavLink to="/discover"><CompassIcon /><span>Discover</span></NavLink>
          <NavLink to="/interests"><SparklesIcon /><span>Interests</span></NavLink>
          <NavLink to="/progress"><ChartIcon /><span>Progress</span></NavLink>
        </nav>
        <div className="user-menu">
          <span className="muted">{user?.display_name || user?.email}</span>
          <ThemeToggle />
          <button className="ghost signout" onClick={logout} aria-label="Sign out">
            <LogoutIcon />
            <span className="signout-label">Sign out</span>
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
