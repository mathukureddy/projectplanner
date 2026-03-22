import { useEffect, useState } from "react";
import { fetchProjects, fetchAlerts, markAlertRead, scanOverdueAlerts } from "../api.js";

export default function AlertsPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    (async () => {
      const p = await fetchProjects();
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id || p[0]._id);
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => setAlerts(await fetchAlerts(projectId)))();
  }, [projectId]);

  async function markRead(id) {
    await markAlertRead(projectId, id, true);
    setAlerts(await fetchAlerts(projectId));
  }

  async function scanNow() {
    setScanning(true);
    try {
      await scanOverdueAlerts(projectId);
      setAlerts(await fetchAlerts(projectId));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div>
      <h2>Alerts</h2>
      <div className="inline-form">
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>{p.name}</option>
          ))}
        </select>
        <button type="button" onClick={scanNow} disabled={!projectId || scanning}>
          {scanning ? "Scanning..." : "Scan overdue"}
        </button>
      </div>

      <div className="data-table" style={{ padding: "0.75rem" }}>
        {alerts.length === 0 ? (
          <p>No alerts.</p>
        ) : (
          alerts.map((a) => (
            <div key={a.id} style={{ opacity: a.read ? 0.65 : 1, marginBottom: "0.6rem" }}>
              <strong>{a.title}</strong> ({a.severity})
              <div>{a.message}</div>
              {!a.read ? (
                <button type="button" onClick={() => markRead(a.id)}>Mark read</button>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

