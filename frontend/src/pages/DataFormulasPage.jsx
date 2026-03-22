import { useEffect, useState } from "react";
import {
  fetchProjects,
  fetchProjectFormulas,
  updateProjectFormulas,
  evaluateProjectFormulas,
  fetchProjectGovernance,
  updateProjectGovernance,
  fetchCellHistory,
} from "../api.js";

export default function DataFormulasPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [formulas, setFormulas] = useState([]);
  const [governance, setGovernance] = useState({ locked_fields: [], restrict_locked_to_admin: true });
  const [lockedFieldsText, setLockedFieldsText] = useState("");
  const [history, setHistory] = useState([]);
  const [newName, setNewName] = useState("");
  const [newTarget, setNewTarget] = useState("percent_complete");
  const [newExpr, setNewExpr] = useState("");

  useEffect(() => {
    (async () => {
      const p = await fetchProjects();
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id || p[0]._id);
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      const [f, g, h] = await Promise.all([
        fetchProjectFormulas(projectId),
        fetchProjectGovernance(projectId),
        fetchCellHistory(projectId, "", "", 50),
      ]);
      setFormulas(f);
      setGovernance(g);
      setLockedFieldsText((g.locked_fields || []).join(", "));
      setHistory(h);
    })();
  }, [projectId]);

  async function saveAll() {
    const gov = {
      ...governance,
      locked_fields: lockedFieldsText.split(",").map((s) => s.trim()).filter(Boolean),
    };
    await Promise.all([
      updateProjectFormulas(projectId, formulas),
      updateProjectGovernance(projectId, gov),
    ]);
    setGovernance(gov);
    setHistory(await fetchCellHistory(projectId, "", "", 50));
  }

  async function evaluateNow() {
    await evaluateProjectFormulas(projectId);
    setHistory(await fetchCellHistory(projectId, "", "", 50));
  }

  return (
    <div>
      <h2>Data Formulas, Governance & History</h2>
      <div className="inline-form">
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="data-table" style={{ padding: "0.75rem", marginBottom: "0.75rem" }}>
        <h4 style={{ marginTop: 0 }}>Formulas</h4>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input placeholder="Target field" value={newTarget} onChange={(e) => setNewTarget(e.target.value)} />
          <input
            placeholder="Expression"
            value={newExpr}
            onChange={(e) => setNewExpr(e.target.value)}
            style={{ minWidth: "22rem" }}
          />
          <button
            type="button"
            onClick={() => {
              if (!newName.trim() || !newTarget.trim() || !newExpr.trim()) return;
              setFormulas((prev) => [
                ...prev,
                { name: newName.trim(), target_field: newTarget.trim(), expression: newExpr.trim(), enabled: true },
              ]);
              setNewName("");
              setNewExpr("");
            }}
          >
            Add
          </button>
        </div>
        <ul>
          {formulas.map((f, idx) => (
            <li key={`${f.name}-${idx}`}>
              <label>
                <input
                  type="checkbox"
                  checked={!!f.enabled}
                  onChange={(e) =>
                    setFormulas((prev) => prev.map((x, i) => (i === idx ? { ...x, enabled: e.target.checked } : x)))
                  }
                />{" "}
                {f.name}: {f.target_field} = {f.expression}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="data-table" style={{ padding: "0.75rem", marginBottom: "0.75rem" }}>
        <h4 style={{ marginTop: 0 }}>Governance</h4>
        <input
          placeholder="Locked fields comma-separated"
          value={lockedFieldsText}
          onChange={(e) => setLockedFieldsText(e.target.value)}
          style={{ minWidth: "24rem" }}
        />
        <div style={{ marginTop: "0.5rem" }}>
          <label>
            <input
              type="checkbox"
              checked={!!governance.restrict_locked_to_admin}
              onChange={(e) => setGovernance((g) => ({ ...g, restrict_locked_to_admin: e.target.checked }))}
            />{" "}
            Restrict locked fields to admin
          </label>
        </div>
      </div>

      <div className="inline-form">
        <button type="button" onClick={saveAll} disabled={!projectId}>Save</button>
        <button type="button" onClick={evaluateNow} disabled={!projectId}>Evaluate formulas</button>
      </div>

      <div className="data-table" style={{ padding: "0.75rem", marginTop: "0.75rem" }}>
        <h4 style={{ marginTop: 0 }}>Cell History</h4>
        {history.length === 0 ? (
          <p>No history yet.</p>
        ) : (
          <ul style={{ margin: 0 }}>
            {history.slice(0, 30).map((h) => (
              <li key={h.id}>
                {h.field}: {h.old_value ?? "-"} → {h.new_value ?? "-"} by {h.changed_by} ({h.source})
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

