import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchProjects, createProject, deleteProject } from "../api.js";

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("On Track");
  const [firstTaskName, setFirstTaskName] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingProjectKey, setDeletingProjectKey] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchProjects();
      setProjects(Array.isArray(data) ? data : []);
    } catch (err) {
      const d = err?.response?.data?.detail;
      const message = Array.isArray(d)
        ? d.map((x) => x.msg || JSON.stringify(x)).join("; ")
        : d || err?.message || "Unable to load projects";
      setError(String(message));
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (creating) return;
    if (!name.trim()) return;
    setCreating(true);
    if (!firstTaskName.trim()) {
      setError("Please add the first task name before creating the project");
      setCreating(false);
      return;
    }
    setError("");
    try {
      const project = await createProject({
        name,
        status,
        tasks: [{ name: firstTaskName.trim() }]
      });
      const projectId = project.id || project._id;
      setName("");
      setFirstTaskName("");
      setProjects((prev) => [...prev, project]);
      navigate(`/projects/${projectId}`);
    } catch (err) {
      const message =
        err?.response?.data?.detail ||
        err?.message ||
        "Unable to create project";
      setError(message);
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(projectKey) {
    if (deletingProjectKey) return;
    const ok = window.confirm("Delete this project and all its tasks?");
    if (!ok) return;

    try {
      setDeletingProjectKey(projectKey);
      await deleteProject(projectKey);
      setProjects((prev) => prev.filter((p) => (p.id || p._id) !== projectKey));
    } catch (err) {
      const message =
        err?.response?.data?.detail ||
        err?.message ||
        "Unable to delete project";
      setError(message);
    } finally {
      setDeletingProjectKey(null);
    }
  }

  return (
    <div>
      <h2>Projects</h2>
      <form onSubmit={handleCreate} className="inline-form">
        <input
          placeholder="New project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="On Track">On Track</option>
          <option value="At Risk">At Risk</option>
          <option value="Off Track">Off Track</option>
        </select>
        <input
          placeholder="First task name (required)"
          value={firstTaskName}
          onChange={(e) => setFirstTaskName(e.target.value)}
        />
        <button type="submit" disabled={creating}>
          {creating ? "Creating..." : "Add"}
        </button>
      </form>
      {error ? <p style={{ color: "crimson" }}>{error}</p> : null}
      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr
                key={p.id || p._id}
                onClick={() => navigate(`/projects/${p.id || p._id}`)}
              >
                <td>{p.name}</td>
                <td>{p.status}</td>
                <td>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(p.id || p._id);
                    }}
                    disabled={deletingProjectKey === (p.id || p._id)}
                  >
                    {deletingProjectKey === (p.id || p._id)
                      ? "Deleting..."
                      : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

