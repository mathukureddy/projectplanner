import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchProject, fetchTasks, createTask } from "../api.js";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskName, setTaskName] = useState("");

  useEffect(() => {
    async function load() {
      const [p, t] = await Promise.all([
        fetchProject(projectId),
        fetchTasks(projectId)
      ]);
      setProject(p);
      setTasks(t);
    }
    load();
  }, [projectId]);

  async function handleAddTask(e) {
    e.preventDefault();
    if (!taskName.trim()) return;
    const task = await createTask({ project_id: projectId, name: taskName });
    setTaskName("");
    setTasks((prev) => [...prev, task]);
  }

  if (!project) return <p>Loading...</p>;

  return (
    <div>
      <h2>{project.name}</h2>
      <p>Status: {project.status}</p>

      <section>
        <h3>Tasks (Grid View)</h3>
        <form onSubmit={handleAddTask} className="inline-form">
          <input
            placeholder="New task name"
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
          />
          <button type="submit">Add</button>
        </form>
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>% Complete</th>
              <th>Assigned To</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td>{t.status}</td>
                <td>{t.percent_complete}%</td>
                <td>{t.assigned_to || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

