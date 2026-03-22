import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchProject,
  fetchTasks,
  createTask,
  updateTask,
  deleteTask,
  snapshotProjectBaseline,
  updateProject,
  fetchComments,
  createComment,
  deleteComment,
  fetchAttachments,
  uploadTaskAttachment,
  deleteAttachment,
  attachmentDownloadUrl,
  fetchAlerts,
  markAlertRead,
  scanOverdueAlerts,
  fetchProjectAutomations,
  updateProjectAutomations,
  runProjectAutomations,
  fetchProjectFormulas,
  updateProjectFormulas,
  evaluateProjectFormulas,
  fetchProjectGovernance,
  updateProjectGovernance,
  fetchCellHistory
} from "../api.js";

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskName, setTaskName] = useState("");
  const [taskStatus, setTaskStatus] = useState("Not Started");
  const [taskStartDate, setTaskStartDate] = useState("");
  const [taskEndDate, setTaskEndDate] = useState("");
  const [taskParentId, setTaskParentId] = useState("");
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

  const [alerts, setAlerts] = useState([]);
  const [scanningAlerts, setScanningAlerts] = useState(false);
  const [shareEmail, setShareEmail] = useState("");
  const [shareRole, setShareRole] = useState("viewer");

  const [commentAuthor, setCommentAuthor] = useState(() =>
    typeof localStorage !== "undefined" ? localStorage.getItem("pp_comment_author") || "" : ""
  );
  const [commentBody, setCommentBody] = useState("");
  const [taskComments, setTaskComments] = useState([]);
  const [taskAttachments, setTaskAttachments] = useState([]);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [sharingOpen, setSharingOpen] = useState(false);
  const [automationsOpen, setAutomationsOpen] = useState(false);
  const [projectAutomations, setProjectAutomations] = useState([]);
  const [savingAutomations, setSavingAutomations] = useState(false);
  const [runningAutomations, setRunningAutomations] = useState(false);
  const [dataFeaturesOpen, setDataFeaturesOpen] = useState(false);
  const [formulas, setFormulas] = useState([]);
  const [newFormulaName, setNewFormulaName] = useState("");
  const [newFormulaTarget, setNewFormulaTarget] = useState("percent_complete");
  const [newFormulaExpr, setNewFormulaExpr] = useState("");
  const [governance, setGovernance] = useState({ locked_fields: [], restrict_locked_to_admin: true });
  const [lockedFieldsText, setLockedFieldsText] = useState("");
  const [cellHistory, setCellHistory] = useState([]);
  const [savingDataFeatures, setSavingDataFeatures] = useState(false);
  const [runningFormulaEval, setRunningFormulaEval] = useState(false);
  const [detailLoading, setDetailLoading] = useState(true);
  const [detailError, setDetailError] = useState("");

  function formatLoadError(err) {
    const d = err?.response?.data?.detail;
    if (Array.isArray(d)) {
      return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
    }
    if (typeof d === "string") return d;
    if (d && typeof d === "object") return JSON.stringify(d);
    if (err?.code === "ECONNABORTED") return "Request timed out — is the backend running and MongoDB up?";
    if (err?.message === "Network Error") return "Cannot reach API — check the backend is running and VITE_API_BASE.";
    return err?.message || "Failed to load project";
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!projectId) {
        setDetailLoading(false);
        setDetailError("Missing project id in URL.");
        setProject(null);
        setTasks([]);
        return;
      }
      setDetailLoading(true);
      setDetailError("");
      try {
        const p = await fetchProject(projectId);
        if (cancelled) return;
        setProject(p);
        try {
          const t = await fetchTasks(projectId);
          if (!cancelled) setTasks(t);
        } catch (te) {
          if (!cancelled) {
            setTasks([]);
            setDetailError(
              `Project loaded, but tasks failed: ${formatLoadError(te)}`
            );
          }
        }
      } catch (e) {
        if (!cancelled) {
          setProject(null);
          setTasks([]);
          setDetailError(formatLoadError(e));
        }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        const [f, g] = await Promise.all([
          fetchProjectFormulas(projectId),
          fetchProjectGovernance(projectId),
        ]);
        setFormulas(Array.isArray(f) ? f : []);
        const gov = g || { locked_fields: [], restrict_locked_to_admin: true };
        setGovernance(gov);
        setLockedFieldsText((gov.locked_fields || []).join(", "));
      } catch {
        setFormulas([]);
      }
    })();
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        setCellHistory(await fetchCellHistory(projectId, selectedTaskKey || "", "", 50));
      } catch {
        setCellHistory([]);
      }
    })();
  }, [projectId, selectedTaskKey, tasks]);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        setAlerts(await fetchAlerts(projectId));
      } catch {
        setAlerts([]);
      }
    })();
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        const autos = await fetchProjectAutomations(projectId);
        setProjectAutomations(Array.isArray(autos) ? autos : []);
      } catch {
        setProjectAutomations([]);
      }
    })();
  }, [projectId]);

  useEffect(() => {
    if (!selectedTaskKey || !projectId) {
      setTaskComments([]);
      setTaskAttachments([]);
      return;
    }
    (async () => {
      try {
        const [c, a] = await Promise.all([
          fetchComments(projectId, selectedTaskKey),
          fetchAttachments(projectId, selectedTaskKey)
        ]);
        setTaskComments(c);
        setTaskAttachments(a);
      } catch {
        setTaskComments([]);
        setTaskAttachments([]);
      }
    })();
  }, [selectedTaskKey, projectId]);

  async function reloadTasks() {
    const t = await fetchTasks(projectId);
    setTasks(t);
    return t;
  }

  const selectedTask = tasks.find(
    (t) => (t.id || t._id) === selectedTaskKey
  );

  useEffect(() => {
    const t = tasks.find((x) => (x.id || x._id) === selectedTaskKey);
    if (!t) return;
    setEditStatus(t.status || "Not Started");
    setEditStartDate(t.start_date || "");
    setEditEndDate(t.end_date || "");
    setEditPredecessors(t.predecessors || []);
    setEditPercentComplete(t.percent_complete ?? 0);
    setEditParentTaskId(t.parent_task_id ? String(t.parent_task_id) : "");
  }, [selectedTaskKey, tasks]);

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
      parent_task_id: taskParentId || null
    });
    setTaskName("");
    setTaskStatus("Not Started");
    setTaskStartDate("");
    setTaskEndDate("");
    setTaskParentId("");
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

  if (detailLoading) {
    return (
      <div>
        <p>Loading project…</p>
        <p style={{ fontSize: "0.9rem", color: "#666" }}>
          If this never finishes, confirm MongoDB is running and the backend uses the same{" "}
          <code>MONGODB_DB</code> as when the project was created.
        </p>
      </div>
    );
  }

  if (detailError && !project) {
    return (
      <div>
        <p style={{ color: "#b02a37" }}>{detailError}</p>
        <p style={{ fontSize: "0.9rem", color: "#444" }}>
          Common causes: backend or MongoDB stopped after restart; or <code>MONGODB_DB</code> /{" "}
          <code>MONGODB_URI</code> differs from before (data lives in the database name you used).
        </p>
        <p>
          <Link to="/">← Back to projects</Link>
        </p>
      </div>
    );
  }

  if (!project) {
    return (
      <div>
        <p>Project not found.</p>
        <p>
          <Link to="/">← Back to projects</Link>
        </p>
      </div>
    );
  }

  async function handleSnapshotBaseline() {
    setSnapshottingBaseline(true);
    try {
      const data = await snapshotProjectBaseline(projectId);
      if (data?.project) {
        setProject(data.project);
      } else {
        setProject(await fetchProject(projectId));
      }
      setTasks(await fetchTasks(projectId));
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = Array.isArray(d)
        ? d.map((x) => x.msg || JSON.stringify(x)).join("; ")
        : d || e.message;
      console.error(e);
      window.alert(String(msg || "Baseline snapshot failed"));
    } finally {
      setSnapshottingBaseline(false);
    }
  }

  async function reloadAlerts() {
    try {
      setAlerts(await fetchAlerts(projectId));
    } catch {
      setAlerts([]);
    }
  }

  function setAutomationEnabled(automationType, enabled) {
    setProjectAutomations((prev) => {
      if (!prev || prev.length === 0) {
        prev = [
          { type: "notify_on_completion", enabled: true },
          { type: "overdue_alert", enabled: true },
        ];
      }
      return prev.map((r) =>
        r.type === automationType ? { ...r, enabled: !!enabled } : r
      );
    });
  }

  async function handleSaveAutomations() {
    setSavingAutomations(true);
    try {
      const payload = {
        automations: projectAutomations.map((r) => ({
          type: r.type,
          enabled: !!r.enabled,
        })),
      };
      const next = await updateProjectAutomations(projectId, payload);
      setProjectAutomations(next);
    } catch (e) {
      const d = e?.response?.data?.detail;
      window.alert(String(d || e.message || "Failed to save automation rules"));
    } finally {
      setSavingAutomations(false);
    }
  }

  async function handleRunAutomationsNow() {
    setRunningAutomations(true);
    try {
      const res = await runProjectAutomations(projectId);
      await reloadAlerts();
      window.alert(
        `Automations run: overdue=${res?.overdue_alerts_created ?? 0}, completion=${res?.completion_alerts_created ?? 0}`
      );
    } catch (e) {
      const d = e?.response?.data?.detail;
      window.alert(String(d || e.message || "Failed to run automations"));
    } finally {
      setRunningAutomations(false);
    }
  }

  async function handleSaveDataFeatures() {
    setSavingDataFeatures(true);
    try {
      const nextGovernance = {
        ...governance,
        locked_fields: lockedFieldsText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const [savedFormulas, savedGov] = await Promise.all([
        updateProjectFormulas(projectId, formulas),
        updateProjectGovernance(projectId, nextGovernance),
      ]);
      setFormulas(Array.isArray(savedFormulas) ? savedFormulas : []);
      setGovernance(savedGov || nextGovernance);
      setLockedFieldsText((savedGov?.locked_fields || nextGovernance.locked_fields || []).join(", "));
      window.alert("Data features saved");
    } catch (e) {
      const d = e?.response?.data?.detail;
      window.alert(String(d || e.message || "Failed to save data features"));
    } finally {
      setSavingDataFeatures(false);
    }
  }

  async function handleEvaluateFormulasNow() {
    setRunningFormulaEval(true);
    try {
      const res = await evaluateProjectFormulas(projectId);
      await reloadTasks();
      setCellHistory(await fetchCellHistory(projectId, selectedTaskKey || "", "", 50));
      window.alert(`Formulas evaluated: ${res?.applied ?? 0} cell updates`);
    } catch (e) {
      const d = e?.response?.data?.detail;
      window.alert(String(d || e.message || "Formula evaluation failed"));
    } finally {
      setRunningFormulaEval(false);
    }
  }

  async function handleScanOverdue() {
    setScanningAlerts(true);
    try {
      await scanOverdueAlerts(projectId);
      await reloadAlerts();
    } finally {
      setScanningAlerts(false);
    }
  }

  async function handleMarkAlertRead(alertId) {
    await markAlertRead(projectId, alertId, true);
    await reloadAlerts();
  }

  async function handleAddShare(e) {
    e.preventDefault();
    if (!shareEmail.trim()) return;
    const next = [...(project.shares || []), { email: shareEmail.trim(), role: shareRole }];
    const p = await updateProject(projectId, { shares: next });
    setProject(p);
    setShareEmail("");
    setShareRole("viewer");
  }

  async function handleRemoveShare(email) {
    const next = (project.shares || []).filter((s) => s.email !== email);
    const p = await updateProject(projectId, { shares: next });
    setProject(p);
  }

  async function handleAddComment(e) {
    e.preventDefault();
    if (!selectedTaskKey || !commentAuthor.trim() || !commentBody.trim()) return;
    localStorage.setItem("pp_comment_author", commentAuthor.trim());
    await createComment(projectId, {
      task_id: selectedTaskKey,
      author: commentAuthor.trim(),
      body: commentBody.trim()
    });
    setCommentBody("");
    setTaskComments(await fetchComments(projectId, selectedTaskKey));
  }

  async function handleDeleteComment(commentId) {
    if (!window.confirm("Delete this comment?")) return;
    await deleteComment(projectId, commentId);
    setTaskComments(await fetchComments(projectId, selectedTaskKey));
  }

  async function handleAttachmentSelected(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !selectedTaskKey) return;
    setUploadingAttachment(true);
    try {
      await uploadTaskAttachment(projectId, selectedTaskKey, file, commentAuthor.trim());
      setTaskAttachments(await fetchAttachments(projectId, selectedTaskKey));
    } finally {
      setUploadingAttachment(false);
    }
  }

  async function handleDeleteAttachment(attId) {
    if (!window.confirm("Delete this attachment?")) return;
    await deleteAttachment(projectId, attId);
    setTaskAttachments(await fetchAttachments(projectId, selectedTaskKey));
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

  const collapseHeaderStyle = {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    width: "100%",
    textAlign: "left",
    background: "#f1f5f9",
    color: "#0f172a",
    border: "1px solid #e2e8f0",
    padding: "0.5rem 0.75rem",
    cursor: "pointer",
    borderRadius: "6px",
    fontSize: "1.1rem",
    fontWeight: 600,
    marginBottom: "0.5rem"
  };

  const unreadAlertCount = alerts.filter((x) => !x.read).length;
  const shareCount = (project.shares || []).length;
  const notifyOnCompletionEnabled =
    projectAutomations.find((x) => x.type === "notify_on_completion")?.enabled ?? true;
  const overdueAlertEnabled =
    projectAutomations.find((x) => x.type === "overdue_alert")?.enabled ?? true;

  return (
    <div>
      {detailError ? (
        <p
          role="alert"
          style={{
            background: "#fff3cd",
            border: "1px solid #ffc107",
            padding: "0.5rem 0.75rem",
            borderRadius: "6px",
            marginBottom: "0.75rem"
          }}
        >
          {detailError}
        </p>
      ) : null}
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
          <select
            value={taskParentId}
            onChange={(e) => setTaskParentId(e.target.value)}
            title="Parent task (optional)"
            aria-label="Parent task"
          >
            <option value="">No parent (top-level)</option>
            {tasks.map((t) => (
              <option key={t.id || t._id} value={t.id || t._id}>
                {t.name}
              </option>
            ))}
          </select>
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
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1rem",
            zIndex: 1000,
          }}
          onClick={() => setSelectedTaskKey(null)}
        >
          <section
            style={{
              width: "min(980px, 95vw)",
              maxHeight: "90vh",
              overflowY: "auto",
              background: "#fff",
              borderRadius: "10px",
              padding: "1rem",
              boxShadow: "0 10px 30px rgba(15, 23, 42, 0.25)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0 }}>Edit Task</h3>
            <div className="inline-form" style={{ marginBottom: 0 }}>
              <button type="button" onClick={() => setSelectedTaskKey(null)}>Cancel</button>
              <button type="button" onClick={() => setSelectedTaskKey(null)}>Close</button>
            </div>
          </div>
          <form onSubmit={handleSaveEdit} className="inline-form" style={{ marginTop: "0.8rem" }}>
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

          <h4 style={{ marginTop: "1.25rem" }}>Comments</h4>
          <form onSubmit={handleAddComment} className="inline-form" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            <input
              placeholder="Your name"
              value={commentAuthor}
              onChange={(e) => setCommentAuthor(e.target.value)}
              onBlur={() => localStorage.setItem("pp_comment_author", commentAuthor)}
              style={{ minWidth: "8rem" }}
            />
            <input
              placeholder="Comment"
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              style={{ minWidth: "14rem", flex: 1 }}
            />
            <button type="submit">Post comment</button>
          </form>
          <div className="data-table" style={{ padding: "0.6rem", marginTop: "0.5rem" }}>
            {taskComments.length === 0 ? (
              <p style={{ margin: 0 }}>No comments yet.</p>
            ) : (
              taskComments.map((c) => (
                <div key={c.id} style={{ marginBottom: "0.5rem" }}>
                  <strong>{c.author}</strong>{" "}
                  <span style={{ fontSize: "0.8rem", color: "#666" }}>{c.created_at}</span>
                  <div>{c.body}</div>
                  <button type="button" onClick={() => handleDeleteComment(c.id)}>
                    Delete
                  </button>
                </div>
              ))
            )}
          </div>

          <h4 style={{ marginTop: "1.25rem" }}>Attachments</h4>
          <div className="inline-form">
            <label>
              <span style={{ marginRight: "0.5rem" }}>Upload file</span>
              <input
                type="file"
                disabled={uploadingAttachment}
                onChange={handleAttachmentSelected}
              />
            </label>
            {uploadingAttachment ? <span>Uploading...</span> : null}
          </div>
          <ul style={{ marginTop: "0.5rem" }}>
            {taskAttachments.length === 0 ? (
              <li>No attachments.</li>
            ) : (
              taskAttachments.map((att) => (
                <li key={att.id}>
                  <a
                    href={attachmentDownloadUrl(att.id, projectId)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {att.filename}
                  </a>{" "}
                  ({Math.round((att.size || 0) / 1024)} KB)
                  <button
                    type="button"
                    style={{ marginLeft: "0.5rem" }}
                    onClick={() => handleDeleteAttachment(att.id)}
                  >
                    Delete
                  </button>
                </li>
              ))
            )}
          </ul>
          </section>
        </div>
      ) : null}
    </div>
  );
}

