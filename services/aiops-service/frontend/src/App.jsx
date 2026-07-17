import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import Header from "./components/Header.jsx";
import IncidentList from "./components/IncidentList.jsx";
import IncidentDetail from "./components/IncidentDetail.jsx";
import FindingsFeed from "./components/FindingsFeed.jsx";

const POLL_MS = 5000;

function usePersistedTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("aiops-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("aiops-theme", theme);
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return [theme, toggle];
}

export default function App() {
  const [theme, toggleTheme] = usePersistedTheme();
  const [tab, setTab] = useState("incidents");

  const [health, setHealth] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [findings, setFindings] = useState([]);

  const [selectedId, setSelectedId] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const selectedIdRef = useRef(selectedId);
  selectedIdRef.current = selectedId;

  const refreshList = useCallback(async () => {
    try {
      const [h, incs] = await Promise.all([api.health(), api.incidents()]);
      setHealth(h);
      setIncidents(incs);
    } catch (err) {
      console.error("poll failed", err);
    }
  }, []);

  const refreshDetail = useCallback(async (id) => {
    if (id == null) return;
    try {
      const inc = await api.incident(id);
      if (selectedIdRef.current === id) setSelectedIncident(inc);
    } catch (err) {
      console.error("detail refresh failed", err);
    }
  }, []);

  const refreshFeed = useCallback(async () => {
    try {
      setFindings(await api.findings());
    } catch (err) {
      console.error("feed refresh failed", err);
    }
  }, []);

  // Poll the list (+ detail, + feed if that tab is active) on a fixed interval.
  useEffect(() => {
    let cancelled = false;

    async function tick() {
      if (cancelled) return;
      await refreshList();
      if (selectedIdRef.current != null) await refreshDetail(selectedIdRef.current);
      if (tab === "feed") await refreshFeed();
    }

    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [refreshList, refreshDetail, refreshFeed, tab]);

  function handleSelect(id) {
    setSelectedId(id);
    setSelectedIncident(null);
    setDetailLoading(true);
    api
      .incident(id)
      .then((inc) => {
        if (selectedIdRef.current === id) setSelectedIncident(inc);
      })
      .catch((err) => console.error(err))
      .finally(() => setDetailLoading(false));
  }

  async function handleRerunRca(id) {
    await api.rerunRca(id);
    await refreshDetail(id);
  }

  async function handleRemediate(id) {
    await api.remediate(id);
    await Promise.all([refreshDetail(id), refreshList()]);
  }

  return (
    <div className="app">
      <Header health={health} theme={theme} onToggleTheme={toggleTheme} />
      <main className="main">
        <section>
          <div className="tabs">
            <button
              className={`tab${tab === "incidents" ? " active" : ""}`}
              onClick={() => setTab("incidents")}
            >
              Incidents
            </button>
            <button
              className={`tab${tab === "feed" ? " active" : ""}`}
              onClick={() => setTab("feed")}
            >
              Findings feed
            </button>
          </div>
          {tab === "incidents" ? (
            <IncidentList incidents={incidents} selectedId={selectedId} onSelect={handleSelect} />
          ) : (
            <FindingsFeed findings={findings} />
          )}
        </section>

        <section className="panel">
          <IncidentDetail
            incident={selectedIncident}
            loading={detailLoading}
            onRerunRca={handleRerunRca}
            onRemediate={handleRemediate}
          />
        </section>
      </main>
    </div>
  );
}
