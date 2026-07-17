export function SeverityBadge({ severity }) {
  return <span className={`badge ${severity}`}>{severity}</span>;
}

export function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

export function EngineBadge({ engine }) {
  if (!engine) return null;
  const label = engine === "claude" ? "Claude RCA" : "Heuristic RCA";
  return <span className={`badge engine-${engine}`}>{label}</span>;
}

export function SeverityDot({ severity }) {
  return <span className={`dot ${severity}`} />;
}

const SOURCE_LABELS = { metrics: "Metrics", logs: "Logs", traces: "Traces" };

export function SourcePill({ source }) {
  return <span className={`source-pill ${source}`}>{SOURCE_LABELS[source] || source}</span>;
}
