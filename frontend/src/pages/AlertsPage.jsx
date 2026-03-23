import { useEffect, useState } from "react";
import { fetchProjects, fetchAlerts, fetchInboxAlerts, markAlertRead, scanOverdueAlerts } from "../api.js";

export default function AlertsPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [inboxUser, setInboxUser] = useState(localStorage.getItem("pp_alert_user") || "");
  const [mode, setMode] = useState("project");

  useEffect(() => {
    (async () => {
      const p = await fetchProjects();
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id || p[0]._id);
    })();
  }, []);

  useEffect(() => {
    (async () => {
      if (mode === "project") {
        if (!projectId) return;
        setAlerts(await fetchAlerts(projectId));
      } else {
        if (!inboxUser.trim()) {
          setAlerts([]);
          return;
        }
        setAlerts(await fetchInboxAlerts(inboxUser.trim()));
      }
    })();
  }, [projectId, mode, inboxUser]);

  async function markRead(id) {
    const targetProjectId = alerts.find((a) => a.id === id)?.project_id || projectId;
    await markAlertRead(targetProjectId, id, true);
    if (mode === "project") setAlerts(await fetchAlerts(projectId));
    else setAlerts(await fetchInboxAlerts(inboxUser.trim()));
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
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="project">By project</option>
          <option value="inbox">My inbox</option>
        </select>
        {mode === "project" ? (
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>{p.name}</option>
          ))}
        </select>
        ) : (
          <input
            placeholder="User / email"
            value={inboxUser}
            onChange={(e) => {
              setInboxUser(e.target.value);
              localStorage.setItem("pp_alert_user", e.target.value);
            }}
          />
        )}
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
              {a.recipient_user ? <div style={{ fontSize: "0.8rem", color: "#666" }}>To: {a.recipient_user}</div> : null}
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

