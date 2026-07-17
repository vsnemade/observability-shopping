// Formats a unix-seconds timestamp as "just now" / "12s ago" / "3m ago" / "2h ago".
export function relativeTime(unixSeconds) {
  if (!unixSeconds) return "—";
  const deltaMs = Date.now() - unixSeconds * 1000;
  const deltaSec = Math.max(0, Math.round(deltaMs / 1000));
  if (deltaSec < 5) return "just now";
  if (deltaSec < 60) return `${deltaSec}s ago`;
  const deltaMin = Math.round(deltaSec / 60);
  if (deltaMin < 60) return `${deltaMin}m ago`;
  const deltaHr = Math.round(deltaMin / 60);
  if (deltaHr < 24) return `${deltaHr}h ago`;
  return new Date(unixSeconds * 1000).toLocaleString();
}

export function absoluteTime(unixSeconds) {
  if (!unixSeconds) return "—";
  return new Date(unixSeconds * 1000).toLocaleString();
}
