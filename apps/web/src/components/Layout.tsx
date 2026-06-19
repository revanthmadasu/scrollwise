import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  ChartIcon,
  CompassIcon,
  HomeIcon,
  LayersIcon,
  LogoutIcon,
  MenuIcon,
  SparklesIcon,
} from "./icons";
import { ThemeToggle } from "./ThemeToggle";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const name = user?.display_name || user?.email;

  // Close the account menu on navigation.
  useEffect(() => setMenuOpen(false), [location.pathname]);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

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
          {user?.is_admin && (
            <NavLink to="/admin/templates"><LayersIcon /><span>Build</span></NavLink>
          )}
        </nav>

        <div className="user-menu">
          {/* Desktop: inline cluster */}
          <div className="user-desktop">
            <span className="muted">{name}</span>
            <ThemeToggle />
            <button className="ghost signout" onClick={logout} aria-label="Sign out">
              <LogoutIcon />
              <span className="signout-label">Sign out</span>
            </button>
          </div>

          {/* Mobile: collapsed account menu */}
          <div className="account" ref={menuRef}>
            <button
              className="account-trigger"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Account menu"
              aria-haspopup="true"
              aria-expanded={menuOpen}
            >
              <MenuIcon />
            </button>
            {menuOpen && (
              <div className="account-menu" role="menu">
                <div className="account-email">{name}</div>
                <div className="account-item account-theme">
                  <span>Theme</span>
                  <ThemeToggle />
                </div>
                <button
                  className="account-item account-signout"
                  onClick={logout}
                  role="menuitem"
                >
                  <LogoutIcon />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
