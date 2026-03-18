import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchProject, fetchTasks, createTask, updateTask } from "../api.js";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskName, setTaskName] = useState("");
  const [taskStatus, setTaskStatus] = useState("Not Started");
  const [taskStartDate, setTaskStartDate] = useState("");
  const [taskEndDate, setTaskEndDate] = useState("");

  const [selectedTaskKey, setSelectedTaskKey] = useState(null);
  const [editStatus, setEditStatus] = useState("Not Started");
  const [editPercentComplete, setEditPercentComplete] = useState(0);
  const [editStartDate, setEditStartDate] = useState("");
  const [editEndDate, setEditEndDate] = useState("");

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

  async function reloadTasks() {
    const t = await fetchTasks(projectId);
    setTasks(t);
    return t;
  }

  const selectedTask = tasks.find(
    (t) => (t.id || t._id) === selectedTaskKey
  );

  useEffect(() => {
    if (!selectedTask) return;
    setEditStatus(selectedTask.status || "Not Started");
    setEditStartDate(selectedTask.start_date || "");
    setEditEndDate(selectedTask.end_date || "");
    setEditPercentComplete(selectedTask.percent_complete ?? 0);
  }, [selectedTaskKey]);

  function handleEditStatusChange(nextStatus) {
    setEditStatus(nextStatus);
    if (nextStatus === "Not Started") setEditPercentComplete(0);
    if (nextStatus === "Complete") setEditPercentComplete(100);
  }

  async function handleAddTask(e) {
    e.preventDefault();
    if (!taskName.trim()) return;
    await createTask({
      project_id: projectId,
      name: taskName,
      status: taskStatus,
      start_date: taskStartDate || null,
      end_date: taskEndDate || null
    });
    setTaskName("");
    setTaskStatus("Not Started");
    setTaskStartDate("");
    setTaskEndDate("");
    await reloadTasks();
  }

  async function handleSaveEdit(e) {
    e.preventDefault();
    if (!selectedTaskKey) return;
    const payload = {
      status: editStatus,
      start_date: editStartDate || null,
      end_date: editEndDate || null
    };
    if (editStatus === "Not Started") payload.percent_complete = 0;
    if (editStatus === "Complete") payload.percent_complete = 100;
    if (editStatus === "In Progress") payload.percent_complete = Number(editPercentComplete);

    await updateTask(selectedTaskKey, payload);
    setSelectedTaskKey(null);
    setEditStatus("Not Started");
    setEditPercentComplete(0);
    setEditStartDate("");
    setEditEndDate("");
    await reloadTasks();
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
          <select value={taskStatus} onChange={(e) => setTaskStatus(e.target.value)}>
            <option value="Not Started">Not Started</option>
            <option value="In Progress">In Progress</option>
            <option value="Complete">Complete</option>
            <option value="Blocked">Blocked</option>
          </select>
          <input
            type="date"
            value={taskStartDate}
            onChange={(e) => setTaskStartDate(e.target.value)}
            title="Start date"
          />
          <input
            type="date"
            value={taskEndDate}
            onChange={(e) => setTaskEndDate(e.target.value)}
            title="End date"
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
              <th>Start</th>
              <th>End</th>
              <th>Edit</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id || t._id}>
                <td>{t.name}</td>
                <td>{t.status}</td>
                <td>{t.percent_complete}%</td>
                <td>{t.assigned_to || "-"}</td>
                <td>{t.start_date || "-"}</td>
                <td>{t.end_date || "-"}</td>
                <td>
                  <button
                    type="button"
                    onClick={() => setSelectedTaskKey(t.id || t._id)}
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {selectedTask ? (
        <section style={{ marginTop: "1.5rem" }}>
          <h3>Edit Task</h3>
          <form onSubmit={handleSaveEdit} className="inline-form">
            <input value={selectedTask.name} disabled />
            <select
              value={editStatus}
              onChange={(e) => handleEditStatusChange(e.target.value)}
            >
              <option value="Not Started">Not Started</option>
              <option value="In Progress">In Progress</option>
              <option value="Complete">Complete</option>
              <option value="Blocked">Blocked</option>
            </select>
            <input
              type="number"
              min={0}
              max={100}
              step={1}
              value={editPercentComplete}
              onChange={(e) => setEditPercentComplete(e.target.value)}
              disabled={editStatus !== "In Progress"}
              title="Completion percentage"
            />
            <input
              type="date"
              value={editStartDate}
              onChange={(e) => setEditStartDate(e.target.value)}
            />
            <input
              type="date"
              value={editEndDate}
              onChange={(e) => setEditEndDate(e.target.value)}
            />
            <button type="submit">Save</button>
          </form>
        </section>
      ) : null}
    </div>
  );
}

