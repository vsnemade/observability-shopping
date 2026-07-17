import { useMemo, useState } from "react";
import { marked } from "marked";
import { EngineBadge } from "./Badge.jsx";

marked.setOptions({ breaks: false });

export default function RcaPanel({ incidentId, rcaEngine, rcaReport, onRerun }) {
  const [busy, setBusy] = useState(false);

  const html = useMemo(() => {
    if (!rcaReport) return "";
    return marked.parse(rcaReport);
  }, [rcaReport]);

  async function handleRerun() {
    setBusy(true);
    try {
      await onRerun(incidentId);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="rca-panel-head">
        <h3 className="section-title" style={{ margin: 0 }}>Root-cause analysis</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <EngineBadge engine={rcaEngine} />
          <button className="btn" onClick={handleRerun} disabled={busy}>
            {busy ? "Running…" : "Re-run RCA"}
          </button>
        </div>
      </div>
      {rcaReport ? (
        <div className="rca-report" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <div className="loading-row">RCA report pending…</div>
      )}
    </div>
  );
}
