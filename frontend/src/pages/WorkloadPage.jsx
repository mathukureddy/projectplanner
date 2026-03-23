import { useEffect, useState } from "react";
import {
  fetchProjects,
  fetchWorkloadReport,
  fetchWorkloadSettings,
  setAssigneeCapacity,
  deleteAssigneeCapacity,
  setRoleCapacity,
  deleteRoleCapacity,
  fetchWorkloadTrend,
} from "../api";

export default function WorkloadPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [windowDays, setWindowDays] = useState(14);
  const [capacityPerDay, setCapacityPerDay] = useState(8);
  const [overThreshold, setOverThreshold] = useState(100);
  const [underThreshold, setUnderThreshold] = useState(60);
  const [report, setReport] = useState(null);
  const [trend, setTrend] = useState(null);
  const [settings, setSettings] = useState({ assignee_capacity_per_day: {}, role_capacity_per_day: {}, assignee_roles: {} });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [assigneeName, setAssigneeName] = useState("");
  const [assigneeCap, setAssigneeCap] = useState(8);
  const [assigneeRole, setAssigneeRole] = useState("");
  const [roleName, setRoleName] = useState("");
  const [roleCap, setRoleCap] = useState(8);

  useEffect(() => {
    (async () => {
      const list = await fetchProjects();
      setProjects(list);
      setProjectId("");
    })();
  }, []);

  const load = async () => {
    setLoading(true);
    setMessage("");
    try {
      const [data, cfg, tr] = await Promise.all([
        fetchWorkloadReport(
          projectId,
          Number(windowDays),
          Number(capacityPerDay),
          Number(overThreshold),
          Number(underThreshold)
        ),
        fetchWorkloadSettings(),
        fetchWorkloadTrend(projectId, 8, Number(capacityPerDay)),
      ]);
      setReport(data);
      setSettings(cfg);
      setTrend(tr);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to load workload report.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [projectId]);

  const saveAssignee = async () => {
    if (!assigneeName.trim()) return;
    try {
      await setAssigneeCapacity(assigneeName.trim(), Number(assigneeCap), assigneeRole.trim());
      await load();
      setMessage("Assignee capacity saved.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to save assignee capacity.");
    }
  };

  const saveRole = async () => {
    if (!roleName.trim()) return;
    try {
      await setRoleCapacity(roleName.trim(), Number(roleCap));
      await load();
      setMessage("Role capacity saved.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to save role capacity.");
    }
  };

  return (
    <section>
      <h2>Workload</h2>
      <p className="muted">Resource utilization and over-allocation view.</p>

      <div className="inline-form" style={{ flexWrap: "wrap" }}>
        <label>
          Project:
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)} style={{ marginLeft: "0.5rem" }}>
            <option value="">All projects</option>
            {projects.map((p) => (
              <option key={p.id || p._id} value={p.id || p._id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Window days:
          <input
            type="number"
            min={1}
            max={90}
            value={windowDays}
            onChange={(e) => setWindowDays(e.target.value)}
            style={{ marginLeft: "0.5rem", width: "5rem" }}
          />
        </label>
        <label>
          Capacity/day:
          <input
            type="number"
            min={1}
            max={24}
            value={capacityPerDay}
            onChange={(e) => setCapacityPerDay(e.target.value)}
            style={{ marginLeft: "0.5rem", width: "5rem" }}
          />
        </label>
        <label>
          Overalloc %:
          <input
            type="number"
            min={50}
            max={300}
            value={overThreshold}
            onChange={(e) => setOverThreshold(e.target.value)}
            style={{ marginLeft: "0.5rem", width: "5rem" }}
          />
        </label>
        <label>
          Underalloc %:
          <input
            type="number"
            min={0}
            max={100}
            value={underThreshold}
            onChange={(e) => setUnderThreshold(e.target.value)}
            style={{ marginLeft: "0.5rem", width: "5rem" }}
          />
        </label>
        <button type="button" onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Capacity settings</h3>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <input placeholder="Assignee (e.g. alice)" value={assigneeName} onChange={(e) => setAssigneeName(e.target.value)} />
          <input
            type="number"
            min={1}
            max={24}
            placeholder="Capacity/day"
            value={assigneeCap}
            onChange={(e) => setAssigneeCap(e.target.value)}
            style={{ width: "7rem" }}
          />
          <input placeholder="Role (optional)" value={assigneeRole} onChange={(e) => setAssigneeRole(e.target.value)} />
          <button type="button" onClick={saveAssignee}>Save assignee</button>
        </div>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <input placeholder="Role (e.g. dev)" value={roleName} onChange={(e) => setRoleName(e.target.value)} />
          <input
            type="number"
            min={1}
            max={24}
            placeholder="Capacity/day"
            value={roleCap}
            onChange={(e) => setRoleCap(e.target.value)}
            style={{ width: "7rem" }}
          />
          <button type="button" onClick={saveRole}>Save role</button>
        </div>
        <p className="muted">Assignee capacities override role capacities.</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div>
            <h4>Assignee capacities</h4>
            {Object.keys(settings.assignee_capacity_per_day || {}).length === 0 ? (
              <p className="muted">None</p>
            ) : (
              <table className="data-table">
                <thead><tr><th>Assignee</th><th>Role</th><th>Cap/day</th><th>Actions</th></tr></thead>
                <tbody>
                  {Object.entries(settings.assignee_capacity_per_day || {}).map(([name, cap]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{(settings.assignee_roles || {})[name] || "-"}</td>
                      <td>{cap}</td>
                      <td><button type="button" onClick={async () => { await deleteAssigneeCapacity(name); await load(); }}>Delete</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div>
            <h4>Role capacities</h4>
            {Object.keys(settings.role_capacity_per_day || {}).length === 0 ? (
              <p className="muted">None</p>
            ) : (
              <table className="data-table">
                <thead><tr><th>Role</th><th>Cap/day</th><th>Actions</th></tr></thead>
                <tbody>
                  {Object.entries(settings.role_capacity_per_day || {}).map(([role, cap]) => (
                    <tr key={role}>
                      <td>{role}</td>
                      <td>{cap}</td>
                      <td><button type="button" onClick={async () => { await deleteRoleCapacity(role); await load(); }}>Delete</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {report ? (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Summary</h3>
          <p className="muted">
            Window: {report.scope.window_start} to {report.scope.window_end} | Assignees: {report.totals.assignee_count}
            {" | "}Over-allocated: {report.totals.overallocated_count}
          </p>
          {report.assignees.length === 0 ? (
            <p className="muted">No active assigned tasks found.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Assignee</th>
                  <th>Role</th>
                  <th>Active tasks</th>
                  <th>Overdue</th>
                  <th>Cap/day</th>
                  <th>Load hours</th>
                  <th>Capacity hours</th>
                  <th>Utilization %</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {report.assignees.map((r) => (
                  <tr key={r.assignee}>
                    <td>{r.assignee}</td>
                    <td>{r.role || "-"}</td>
                    <td>{r.active_task_count}</td>
                    <td>{r.overdue_task_count}</td>
                    <td>{r.capacity_hours_per_day}</td>
                    <td>{r.load_hours}</td>
                    <td>{r.capacity_hours}</td>
                    <td>{r.utilization_percent}</td>
                    <td>{r.allocation_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {trend ? (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>Weekly trend (next 8 weeks)</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Week start</th>
                <th>Week end</th>
                <th>Assignees</th>
                <th>Avg utilization %</th>
                <th>Overallocated</th>
                <th>Underallocated</th>
              </tr>
            </thead>
            <tbody>
              {(trend.points || []).map((p) => (
                <tr key={p.week_start}>
                  <td>{p.week_start}</td>
                  <td>{p.week_end}</td>
                  <td>{p.assignee_count}</td>
                  <td>{p.avg_utilization_percent}</td>
                  <td>{p.overallocated_count}</td>
                  <td>{p.underallocated_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {message ? <p style={{ marginTop: "0.75rem" }}>{message}</p> : null}
    </section>
  );
}

