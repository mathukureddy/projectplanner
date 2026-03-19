import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  fetchProject,
  fetchTasks,
  createTask,
  updateTask,
  deleteTask,
  snapshotProjectBaseline
} from "../api.js";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskName, setTaskName] = useState("");
  const [taskStatus, setTaskStatus] = useState("Not Started");
  const [taskStartDate, setTaskStartDate] = useState("");
  const [taskEndDate, setTaskEndDate] = useState("");
  const [viewMode, setViewMode] = useState("grid");

  const [selectedTaskKey, setSelectedTaskKey] = useState(null);
  const [editStatus, setEditStatus] = useState("Not Started");
  const [editPercentComplete, setEditPercentComplete] = useState(0);
  const [editStartDate, setEditStartDate] = useState("");
  const [editEndDate, setEditEndDate] = useState("");
  const [editPredecessors, setEditPredecessors] = useState([]);
  const [editParentTaskId, setEditParentTaskId] = useState("");
  const [snapshottingBaseline, setSnapshottingBaseline] = useState(false);
  const [deletingTaskKey, setDeletingTaskKey] = useState(null);

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
    setEditPredecessors(selectedTask.predecessors || []);
    setEditPercentComplete(selectedTask.percent_complete ?? 0);
    setEditParentTaskId(selectedTask.parent_task_id || "");
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
      end_date: taskEndDate || null,
      predecessors: [],
      parent_task_id: null
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
      end_date: editEndDate || null,
      predecessors: editPredecessors,
      parent_task_id: editParentTaskId || null
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
    setEditPredecessors([]);
    setEditParentTaskId("");
    await reloadTasks();
  }

  async function handleDeleteTask(taskKey) {
    if (!taskKey) return;
    if (!window.confirm("Delete this task?")) return;
    setDeletingTaskKey(taskKey);
    try {
      await deleteTask(taskKey);
      if (selectedTaskKey === taskKey) {
        setSelectedTaskKey(null);
        setEditStatus("Not Started");
        setEditPercentComplete(0);
        setEditStartDate("");
        setEditEndDate("");
        setEditPredecessors([]);
        setEditParentTaskId("");
      }
      await reloadTasks();
    } finally {
      setDeletingTaskKey(null);
    }
  }

  if (!project) return <p>Loading...</p>;

  async function handleSnapshotBaseline() {
    setSnapshottingBaseline(true);
    try {
      await snapshotProjectBaseline(projectId);
      const [p, t] = await Promise.all([fetchProject(projectId), fetchTasks(projectId)]);
      setProject(p);
      setTasks(t);
    } finally {
      setSnapshottingBaseline(false);
    }
  }

  const tasksById = Object.fromEntries(tasks.map((t) => [t.id || t._id, t]));
  const childMap = tasks.reduce((acc, t) => {
    const parentId = t.parent_task_id;
    if (parentId && tasksById[parentId]) {
      if (!acc[parentId]) acc[parentId] = [];
      acc[parentId].push(t);
    }
    return acc;
  }, {});

  const visited = new Set();
  const hierarchyOrderedTasks = [];
  function pushNode(task, level) {
    const key = task.id || task._id;
    if (visited.has(key)) return;
    visited.add(key);
    hierarchyOrderedTasks.push({ ...task, hierarchyLevel: level });
    const children = (childMap[key] || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    children.forEach((child) => pushNode(child, level + 1));
  }
  tasks
    .filter((t) => !t.parent_task_id || !tasksById[t.parent_task_id])
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((root) => pushNode(root, 0));
  tasks.forEach((t) => {
    if (!visited.has(t.id || t._id)) pushNode(t, 0);
  });

  const availableParents = tasks
    .filter((t) => (t.id || t._id) !== selectedTaskKey)
    .map((t) => ({ id: t.id || t._id, name: t.name }));

  const availablePredecessors = tasks
    .filter((t) => (t.id || t._id) !== selectedTaskKey)
    .map((t) => ({ id: t.id || t._id, name: t.name }));

  const ganttTasks = hierarchyOrderedTasks
    .map((t) => {
      const start = t.start_date ? new Date(t.start_date) : null;
      const end = t.end_date ? new Date(t.end_date) : null;
      return { ...t, _start: start, _end: end };
    })
    .filter((t) => t._start && t._end && t._end >= t._start);

  const ganttMinStart =
    ganttTasks.length > 0
      ? new Date(Math.min(...ganttTasks.map((t) => t._start.getTime())))
      : null;
  const ganttMaxEnd =
    ganttTasks.length > 0
      ? new Date(Math.max(...ganttTasks.map((t) => t._end.getTime())))
      : null;

  function diffDays(a, b) {
    return Math.max(0, Math.round((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24)));
  }

  const totalDays =
    ganttMinStart && ganttMaxEnd ? Math.max(1, diffDays(ganttMinStart, ganttMaxEnd) + 1) : 1;

  const cardColumns = ["Not Started", "In Progress", "Blocked", "Complete"];

  const calendarMap = tasks.reduce((acc, t) => {
    const key = t.end_date || t.start_date || "No Date";
    if (!acc[key]) acc[key] = [];
    acc[key].push(t);
    return acc;
  }, {});

  const calendarKeys = Object.keys(calendarMap).sort((a, b) => {
    if (a === "No Date") return 1;
    if (b === "No Date") return -1;
    return new Date(a).getTime() - new Date(b).getTime();
  });

  return (
    <div>
      <h2>{project.name}</h2>
      <p>Status: {project.status}</p>
      <p>
        Baseline: {project.baseline_start || "-"} to {project.baseline_end || "-"} | Schedule:{" "}
        {project.schedule_status || "No Baseline"}
        {project.baseline_variance_days !== null && project.baseline_variance_days !== undefined
          ? ` (${project.baseline_variance_days >= 0 ? "+" : ""}${project.baseline_variance_days} days)`
          : ""}
      </p>
      <button type="button" onClick={handleSnapshotBaseline} disabled={snapshottingBaseline}>
        {snapshottingBaseline ? "Saving Baseline..." : "Set Current Plan as Baseline"}
      </button>

      <section>
        <h3>Tasks</h3>
        <div className="inline-form" style={{ marginBottom: "0.75rem" }}>
          <button type="button" onClick={() => setViewMode("grid")} disabled={viewMode === "grid"}>
            Grid
          </button>
          <button type="button" onClick={() => setViewMode("gantt")} disabled={viewMode === "gantt"}>
            Gantt
          </button>
          <button type="button" onClick={() => setViewMode("card")} disabled={viewMode === "card"}>
            Card
          </button>
          <button type="button" onClick={() => setViewMode("calendar")} disabled={viewMode === "calendar"}>
            Calendar
          </button>
        </div>

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

        {viewMode === "grid" ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>% Complete</th>
                <th>Assigned To</th>
                <th>Start</th>
                <th>End</th>
                <th>Dependencies</th>
                <th>Critical</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {hierarchyOrderedTasks.map((t) => (
                <tr key={t.id || t._id}>
                  <td>
                    {"\u00A0".repeat((t.hierarchyLevel || t.hierarchy_level || 0) * 4)}
                    {((t.child_count ?? 0) > 0) ? "▾ " : ""}
                    {t.name}
                  </td>
                  <td>{t.status}</td>
                  <td>{t.percent_complete}%</td>
                  <td>{t.assigned_to || "-"}</td>
                  <td>{t.start_date || "-"}</td>
                  <td>{t.end_date || "-"}</td>
                  <td>{(t.predecessors || []).length}</td>
                  <td>
                    {t.is_critical ? "Yes" : "No"}
                    {t.slack_days !== undefined && t.slack_days !== null ? ` (slack ${t.slack_days})` : ""}
                  </td>
                  <td>
                    {(t.child_count ?? 0) > 0 ? (
                      <div style={{ fontSize: "0.8rem", marginBottom: "0.3rem" }}>
                        Rollup: {t.rollup_status} ({t.rollup_percent_complete}%)
                      </div>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => setSelectedTaskKey(t.id || t._id)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteTask(t.id || t._id)}
                      disabled={deletingTaskKey === (t.id || t._id)}
                      style={{ marginLeft: "0.5rem" }}
                    >
                      {deletingTaskKey === (t.id || t._id) ? "Deleting..." : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}

        {viewMode === "gantt" ? (
          <div className="data-table" style={{ padding: "0.75rem" }}>
            {ganttTasks.length === 0 ? (
              <p>Add start and end dates to see Gantt timeline.</p>
            ) : (
              ganttTasks.map((t) => {
                const offsetPct = (diffDays(ganttMinStart, t._start) / totalDays) * 100;
                const widthPct = (Math.max(1, diffDays(t._start, t._end) + 1) / totalDays) * 100;
                return (
                  <div key={t.id || t._id} style={{ marginBottom: "0.6rem" }}>
                    <div style={{ fontSize: "0.9rem", marginBottom: "0.2rem" }}>
                      {"\u00A0".repeat((t.hierarchyLevel || t.hierarchy_level || 0) * 4)}
                      {t.name} ({t.start_date} - {t.end_date})
                    </div>
                    <div style={{ background: "#eef2ff", height: "16px", borderRadius: "8px", position: "relative" }}>
                      <div
                        style={{
                          position: "absolute",
                          left: `${offsetPct}%`,
                          width: `${Math.max(2, widthPct)}%`,
                          height: "16px",
                          borderRadius: "8px",
                          background: t.is_critical ? "#dc3545" : "#0d6efd",
                        }}
                        title={`${t.name}: ${t.status}${t.is_critical ? " | Critical" : ""}`}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        ) : null}

        {viewMode === "card" ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: "0.75rem" }}>
            {cardColumns.map((statusCol) => (
              <div key={statusCol} className="data-table" style={{ padding: "0.6rem" }}>
                <h4 style={{ marginTop: 0, marginBottom: "0.5rem" }}>{statusCol}</h4>
                {hierarchyOrderedTasks.filter((t) => t.status === statusCol).map((t) => (
                  <div
                    key={t.id || t._id}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e5e7eb",
                      borderRadius: "6px",
                      padding: "0.5rem",
                      marginBottom: "0.5rem",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {"\u00A0".repeat((t.hierarchyLevel || t.hierarchy_level || 0) * 2)}
                      {t.name}
                    </div>
                    <div style={{ fontSize: "0.85rem" }}>{t.percent_complete}% complete</div>
                    {(t.child_count ?? 0) > 0 ? (
                      <div style={{ fontSize: "0.8rem" }}>
                        Rollup: {t.rollup_status} ({t.rollup_percent_complete}%)
                      </div>
                    ) : null}
                    <div style={{ fontSize: "0.8rem" }}>
                      Deps: {(t.predecessors || []).length} | {t.is_critical ? "Critical" : `Slack ${t.slack_days ?? 0}`}
                    </div>
                    <div style={{ fontSize: "0.85rem" }}>{t.start_date || "-"} to {t.end_date || "-"}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : null}

        {viewMode === "calendar" ? (
          <div className="data-table" style={{ padding: "0.75rem" }}>
            {calendarKeys.length === 0 ? (
              <p>No tasks yet.</p>
            ) : (
              calendarKeys.map((dateKey) => (
                <div key={dateKey} style={{ marginBottom: "0.8rem" }}>
                  <div style={{ fontWeight: 700, marginBottom: "0.3rem" }}>
                    {dateKey}
                  </div>
                  {calendarMap[dateKey].map((t) => (
                    <div
                      key={t.id || t._id}
                      style={{
                        background: "#f8fafc",
                        border: "1px solid #e5e7eb",
                        borderRadius: "6px",
                        padding: "0.45rem",
                        marginBottom: "0.35rem",
                      }}
                    >
                      {t.name} - {t.status} ({t.percent_complete}%)
                      {(t.child_count ?? 0) > 0
                        ? ` | Rollup: ${t.rollup_status} (${t.rollup_percent_complete}%)`
                        : ""}
                      {t.is_critical ? " | Critical" : ""}
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        ) : null}
      </section>

      <section style={{ marginTop: "1.2rem" }}>
        <h3>Dependency Graph</h3>
        <div className="data-table" style={{ padding: "0.75rem" }}>
          {tasks.filter((t) => (t.predecessors || []).length > 0).length === 0 ? (
            <p>No dependencies set yet.</p>
          ) : (
            tasks
              .filter((t) => (t.predecessors || []).length > 0)
              .map((t) => (
                <div key={t.id || t._id} style={{ marginBottom: "0.4rem" }}>
                  <strong>{t.name}</strong>:{" "}
                  {(t.predecessors || [])
                    .map((pid) => tasks.find((x) => (x.id || x._id) === pid)?.name || pid)
                    .join(", ")}
                </div>
              ))
          )}
        </div>
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
            <select
              value={editParentTaskId}
              onChange={(e) => setEditParentTaskId(e.target.value)}
            >
              <option value="">No parent (top-level)</option>
              {availableParents.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <select
              multiple
              value={editPredecessors}
              onChange={(e) =>
                setEditPredecessors(Array.from(e.target.selectedOptions).map((o) => o.value))
              }
            >
              {availablePredecessors.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <button type="submit">Save</button>
          </form>
        </section>
      ) : null}
    </div>
  );
}

