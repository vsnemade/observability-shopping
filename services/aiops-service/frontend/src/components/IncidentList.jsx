import { relativeTime } from "../utils/time.js";
import { SeverityDot, StatusBadge, SourcePill } from "./Badge.jsx";
import EmptyState from "./EmptyState.jsx";

function uniqueSources(findings) {
  return [...new Set(findings.map((f) => f.source))];
}

function IncidentCard({ incident, selected, onSelect }) {
  return (
    <button
      className={`incident-card${selected ? " selected" : ""}`}
      onClick={() => onSelect(incident.id)}
    >
      <div className="incident-card-top">
        <div className="incident-card-service">
          <SeverityDot severity={incident.severity} />
          <span className="truncate">{incident.service}</span>
        </div>
        <StatusBadge status={incident.status} />
      </div>
      <div className="source-pills">
        {uniqueSources(incident.findings).map((s) => (
          <SourcePill key={s} source={s} />
        ))}
      </div>
      <div className="incident-card-meta">
        <span>#{incident.id} · {incident.findings.length} finding{incident.findings.length === 1 ? "" : "s"}</span>
        <span>{relativeTime(incident.updated_at)}</span>
      </div>
    </button>
  );
}

export default function IncidentList({ incidents, selectedId, onSelect }) {
  if (!incidents.length) {
    return (
      <EmptyState
        icon="✓"
        title="No incidents detected yet"
        hint="Generate traffic or break a service — the detection loop runs every 30s."
      />
    );
  }

  const sorted = [...incidents].sort((a, b) => {
    if (a.status !== b.status) return a.status === "open" ? -1 : 1;
    return b.updated_at - a.updated_at;
  });

  return (
    <div className="incident-list">
      {sorted.map((inc) => (
        <IncidentCard
          key={inc.id}
          incident={inc}
          selected={inc.id === selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
