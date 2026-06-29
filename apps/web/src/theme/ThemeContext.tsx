import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

// Theme preference. "system" follows the OS / browser setting and updates live.
export type ThemePref = "light" | "dark" | "system";

const STORAGE_KEY = "scrollwise-theme";

function effective(pref: ThemePref): "light" | "dark" {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref;
}

// Apply the resolved theme to <html data-theme>; the CSS keys off this attribute.
function apply(pref: ThemePref) {
  document.documentElement.setAttribute("data-theme", effective(pref));
}

// `theme` is the user's preference; `resolved` is the actual light/dark in
// effect right now (preference "system" resolved against the OS setting).
type ThemeCtx = {
  theme: ThemePref;
  resolved: "light" | "dark";
  setTheme: (t: ThemePref) => void;
};
const ThemeContext = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemePref>(
    () => (localStorage.getItem(STORAGE_KEY) as ThemePref | null) ?? "system"
  );
  const [resolved, setResolved] = useState<"light" | "dark">(() => effective(theme));

  useEffect(() => {
    apply(theme);
    setResolved(effective(theme));
  }, [theme]);

  // While on "system", re-apply when the OS theme flips (e.g. day/night auto).
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      apply("system");
      setResolved(effective("system"));
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = (t: ThemePref) => {
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  };

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
