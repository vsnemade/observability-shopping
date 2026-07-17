import { SourcePill, SeverityDot } from "./Badge.jsx";
import { relativeTime } from "../utils/time.js";
import EmptyState from "./EmptyState.jsx";

export default function FindingsFeed({ findings }) {
  if (!findings.length) {
    return (
      <EmptyState
        icon="◌"
        title="No findings yet"
        hint="Raw output from the detectors before correlation/dedup — every 30s cycle."
      />
    );
  }

  const sorted = [...findings].sort((a, b) => b.timestamp - a.timestamp);

  return (
    <div className="feed-list">
      {sorted.map((f) => (
        <div className="feed-item" key={f.id}>
          <SeverityDot severity={f.severity} />
          <div className="feed-item-body">
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 3 }}>
              <SourcePill source={f.source} />
              <strong style={{ fontSize: 13 }}>{f.service}</strong>
            </div>
            <div className="feed-item-detail">{f.detail}</div>
          </div>
          <span className="feed-item-time">{relativeTime(f.timestamp)}</span>
        </div>
      ))}
    </div>
  );
}
