// Thin fetch wrapper around the aiops-service REST API. Same-origin in
// production (FastAPI serves both); proxied in dev (see vite.config.js).

async function req(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${options?.method || "GET"} ${path} -> ${res.status}: ${body}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => req("/health"),
  incidents: () => req("/incidents"),
  incident: (id) => req(`/incidents/${id}`),
  findings: () => req("/findings"),
  rerunRca: (id) => req(`/incidents/${id}/rca`, { method: "POST" }),
  remediate: (id) => req(`/incidents/${id}/remediate`, { method: "POST" }),
};
