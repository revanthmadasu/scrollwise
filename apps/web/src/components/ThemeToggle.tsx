import type { ThemePref } from "../theme/ThemeContext";
import { useTheme } from "../theme/ThemeContext";
import { MonitorIcon, MoonIcon, SunIcon } from "./icons";

const OPTIONS: { value: ThemePref; label: string; Icon: (p: { size?: number }) => JSX.Element }[] = [
  { value: "light", label: "Light", Icon: SunIcon },
  { value: "dark", label: "Dark", Icon: MoonIcon },
  { value: "system", label: "System (browser default)", Icon: MonitorIcon },
];

// Segmented light / dark / system control.
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          className={theme === value ? "active" : ""}
          aria-pressed={theme === value}
          title={label}
          aria-label={label}
          onClick={() => setTheme(value)}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
