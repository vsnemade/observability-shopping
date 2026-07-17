import { SourcePill, SeverityDot } from "./Badge.jsx";
import { absoluteTime } from "../utils/time.js";

export default function FindingItem({ finding }) {
  const hasEvidence = finding.evidence && Object.keys(finding.evidence).length > 0;
  return (
    <div className="finding-item">
      <div className="finding-item-head">
        <SourcePill source={finding.source} />
        <SeverityDot severity={finding.severity} />
        <span style={{ fontSize: 12, color: "var(--muted)" }}>{absoluteTime(finding.timestamp)}</span>
      </div>
      <div className="finding-detail">{finding.detail}</div>
      {hasEvidence && (
        <details className="finding-evidence">
          <summary>Raw evidence</summary>
          <pre>{JSON.stringify(finding.evidence, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
