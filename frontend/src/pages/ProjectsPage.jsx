import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchProjects, createProject } from "../api.js";

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [status, setStatus] = useState("On Track");
  const [tasksText, setTasksText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function load() {
    setLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    const taskNames = tasksText
      .split("\n")
      .map((t) => t.trim())
      .filter(Boolean);
    if (taskNames.length < 1) {
      setError("Please add at least one task (one task per line) before creating the project");
      return;
    }
    setError("");
    try {
      const tasks = taskNames.map((taskName) => ({ name: taskName }));
      const project = await createProject({
        name,
        status,
        tasks
      });
      setName("");
      setTasksText("");
      setProjects((prev) => [...prev, project]);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      const message =
        err?.response?.data?.detail ||
        err?.message ||
        "Unable to create project";
      setError(message);
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
        <textarea
          placeholder={"Tasks (one per line):\n- Task A\n- Task B"}
          value={tasksText}
          onChange={(e) => setTasksText(e.target.value)}
        />
        <button type="submit">Add</button>
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
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)}>
                <td>{p.name}</td>
                <td>{p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

