import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPortfolioReport, fetchProjectReport } from "../api.js";

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [projectReport, setProjectReport] = useState(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const r = await fetchPortfolioReport();
        setData(r);
      } catch (e) {
        setError(e?.response?.data?.detail || e?.message || "Unable to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleLoadProjectReport() {
    if (!selectedProjectId) {
      setProjectReport(null);
      return;
    }
    try {
      const r = await fetchProjectReport(selectedProjectId);
      setProjectReport(r);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Unable to load project report");
    }
  }

  if (loading) return <p>Loading dashboard...</p>;
  if (error && !data) return <p style={{ color: "crimson" }}>{String(error)}</p>;
  if (!data) return <p>No data.</p>;

  const t = data.totals || {};
  const status = data.project_status_breakdown || {};
  const projects = data.projects || [];

  return (
    <div>
      <h2>Dashboard</h2>
      {error ? <p style={{ color: "crimson" }}>{String(error)}</p> : null}

      <div className="inline-form" style={{ flexWrap: "wrap", marginBottom: "1rem" }}>
        <div className="data-table" style={{ padding: "0.75rem", minWidth: "11rem" }}>
          <strong>Projects</strong>
          <div>{t.project_count ?? 0}</div>
        </div>
        <div className="data-table" style={{ padding: "0.75rem", minWidth: "11rem" }}>
          <strong>Tasks</strong>
          <div>{t.task_count ?? 0}</div>
        </div>
        <div className="data-table" style={{ padding: "0.75rem", minWidth: "11rem" }}>
          <strong>Completion %</strong>
          <div>{t.completion_rate ?? 0}</div>
        </div>
        <div className="data-table" style={{ padding: "0.75rem", minWidth: "11rem" }}>
          <strong>Overdue Tasks</strong>
          <div>{t.overdue_task_count ?? 0}</div>
        </div>
      </div>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Portfolio Rollups</h3>
        <div className="data-table" style={{ padding: "0.75rem" }}>
          <div>On Track: {status["On Track"] ?? 0}</div>
          <div>At Risk: {status["At Risk"] ?? 0}</div>
          <div>Off Track: {status["Off Track"] ?? 0}</div>
          <div>Other: {status["Other"] ?? 0}</div>
        </div>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>Project Reporting</h3>
        <div className="inline-form">
          <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)}>
            <option value="">Select project...</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.project_name}
              </option>
            ))}
          </select>
          <button type="button" onClick={handleLoadProjectReport}>
            Load Report
          </button>
        </div>
        {projectReport ? (
          <div className="data-table" style={{ padding: "0.75rem" }}>
            <div>
              <strong>{projectReport.project?.name}</strong> ({projectReport.project?.status})
            </div>
            <div>Tasks: {projectReport.totals?.task_count ?? 0}</div>
            <div>Completed: {projectReport.totals?.completed_task_count ?? 0}</div>
            <div>Overdue: {projectReport.totals?.overdue_task_count ?? 0}</div>
            <div>Critical: {projectReport.totals?.critical_task_count ?? 0}</div>
            <div>Completion %: {projectReport.totals?.completion_rate ?? 0}</div>
          </div>
        ) : null}
      </section>

      <section>
        <h3>Projects Table</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Project</th>
              <th>Status</th>
              <th>Tasks</th>
              <th>Completed</th>
              <th>Overdue</th>
              <th>Completion %</th>
              <th>Open</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.project_id}>
                <td>{p.project_name}</td>
                <td>{p.status}</td>
                <td>{p.task_count}</td>
                <td>{p.completed_task_count}</td>
                <td>{p.overdue_task_count}</td>
                <td>{p.completion_rate}</td>
                <td>
                  <Link to={`/projects/${p.project_id}`}>View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

