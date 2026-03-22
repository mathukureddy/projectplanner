import { useEffect, useState } from "react";
import {
  fetchProjects,
  fetchProjectAutomations,
  updateProjectAutomations,
  runProjectAutomations,
} from "../api.js";

export default function AutomationRulesPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [rules, setRules] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    (async () => {
      const p = await fetchProjects();
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id || p[0]._id);
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => setRules(await fetchProjectAutomations(projectId)))();
  }, [projectId]);

  async function saveRules() {
    setBusy(true);
    try {
      const saved = await updateProjectAutomations(projectId, { automations: rules });
      setRules(saved);
      setMsg("Saved");
    } finally {
      setBusy(false);
    }
  }

  async function runNow() {
    setBusy(true);
    try {
      const r = await runProjectAutomations(projectId);
      setMsg(`Run complete: overdue=${r.overdue_alerts_created}, completion=${r.completion_alerts_created}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>Automation Rules</h2>
      <div className="inline-form">
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      <div className="data-table" style={{ padding: "0.75rem", marginBottom: "0.75rem" }}>
        {rules.map((r, idx) => (
          <label key={`${r.type}-${idx}`} style={{ display: "block", marginBottom: "0.5rem" }}>
            <input
              type="checkbox"
              checked={!!r.enabled}
              onChange={(e) =>
                setRules((prev) =>
                  prev.map((x, i) => (i === idx ? { ...x, enabled: e.target.checked } : x))
                )
              }
            />{" "}
            {r.type}
          </label>
        ))}
      </div>
      <div className="inline-form">
        <button type="button" onClick={saveRules} disabled={busy || !projectId}>
          Save
        </button>
        <button type="button" onClick={runNow} disabled={busy || !projectId}>
          Run now
        </button>
      </div>
      {msg ? <p>{msg}</p> : null}
    </div>
  );
}

