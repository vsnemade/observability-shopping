export default function EmptyState({ icon = "◌", title, hint }) {
  return (
    <div className="empty-state">
      <div className="icon">{icon}</div>
      <div>{title}</div>
      {hint && <div style={{ fontSize: 12.5 }}>{hint}</div>}
    </div>
  );
}
