import { useState } from "react";

export default function ActionsPanel({ incidentId, actions, remediationLog, onRemediate }) {
  const [busy, setBusy] = useState(false);
  const hasAutoExecutable = actions?.some((a) => a.auto_executable);

  async function handleExecute() {
    setBusy(true);
    try {
      await onRemediate(incidentId);
    } finally {
      setBusy(false);
    }
  }

  if (!actions || actions.length === 0) return null;

  return (
    <div>
      <h3 className="section-title">Suggested actions</h3>
      <div className="actions-list">
        {actions.map((a, i) => (
          <div className="action-item" key={i}>
            <div className="action-text">
              <div className="action-name">{a.action.replaceAll("_", " ")}</div>
              <div>{a.reason}</div>
            </div>
            {a.auto_executable && (
              <button className="btn primary" onClick={handleExecute} disabled={busy}>
                {busy ? "Running…" : "Execute"}
              </button>
            )}
          </div>
        ))}
      </div>
      {!hasAutoExecutable && (
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
          No auto-executable action for this incident — auto-remediation only handles known,
          safe failure signatures (e.g. a service unreachable by Prometheus).
        </div>
      )}
      {remediationLog?.length > 0 && (
        <div className="remediation-log">
          {remediationLog.map((line, i) => (
            <div key={i}>✓ {line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
