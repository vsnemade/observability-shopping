import { relativeTime } from "../utils/time.js";

export default function Header({ health, theme, onToggleTheme }) {
  const rcaOn = health?.llm_rca_enabled;
  const autoOn = health?.auto_remediate;

  return (
    <header className="header">
      <div className="header-title">
        <h1>AIOps</h1>
        <span className="subtitle">Shop Platform observability lab</span>
      </div>

      <div className="health-chips">
        {health && (
          <>
            <span className="chip">
              <span className="dot" style={{ background: "var(--muted)" }} />
              {health.cycles} cycles · last {relativeTime(health.last_cycle_at)}
            </span>
            <span className={`chip ${rcaOn ? "on" : "off"}`}>
              <span className="dot" />
              {rcaOn ? "Claude RCA" : "Heuristic RCA"}
            </span>
            <span className={`chip ${autoOn ? "on" : "off"}`}>
              <span className="dot" />
              Auto-remediate {autoOn ? "on" : "off"}
            </span>
            {health.last_error && (
              <span className="chip" style={{ color: "var(--critical)" }}>
                loop error: {health.last_error}
              </span>
            )}
          </>
        )}
        <button className="theme-toggle" onClick={onToggleTheme} title="Toggle theme">
          {theme === "dark" ? "☾ Dark" : "☀ Light"}
        </button>
      </div>
    </header>
  );
}
