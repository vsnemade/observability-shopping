import { SeverityBadge, StatusBadge } from "./Badge.jsx";
import { absoluteTime } from "../utils/time.js";
import FindingItem from "./FindingItem.jsx";
import RcaPanel from "./RcaPanel.jsx";
import ActionsPanel from "./ActionsPanel.jsx";
import EmptyState from "./EmptyState.jsx";

export default function IncidentDetail({ incident, loading, onRerunRca, onRemediate }) {
  if (!incident && loading) {
    return <div className="loading-row">Loading incident…</div>;
  }

  if (!incident) {
    return (
      <EmptyState
        icon="←"
        title="Select an incident"
        hint="Pick one from the list to see findings, suggested actions, and the RCA report."
      />
    );
  }

  return (
    <div className="detail">
      <div className="detail-header">
        <div>
          <h2>{incident.service}</h2>
          <div className="detail-timestamps">
            #{incident.id} · opened {absoluteTime(incident.started_at)} · updated{" "}
            {absoluteTime(incident.updated_at)}
          </div>
        </div>
        <div className="detail-badges">
          <SeverityBadge severity={incident.severity} />
          <StatusBadge status={incident.status} />
        </div>
      </div>

      <div>
        <h3 className="section-title">
          Findings ({incident.findings.length})
        </h3>
        <div className="findings-list">
          {incident.findings.map((f) => (
            <FindingItem key={f.id} finding={f} />
          ))}
        </div>
      </div>

      <ActionsPanel
        incidentId={incident.id}
        actions={incident.suggested_actions}
        remediationLog={incident.remediation_log}
        onRemediate={onRemediate}
      />

      <RcaPanel
        incidentId={incident.id}
        rcaEngine={incident.rca_engine}
        rcaReport={incident.rca_report}
        onRerun={onRerunRca}
      />
    </div>
  );
}
