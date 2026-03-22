import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("pp_auth_token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function login(username, password) {
  const res = await api.post("/auth/login", { username, password });
  return res.data;
}

export async function register(username, email, password, role = "editor") {
  const res = await api.post("/auth/register", { username, email, password, role });
  return res.data;
}

export async function fetchMe() {
  const res = await api.get("/auth/me");
  return res.data;
}

export async function fetchAdminUsers() {
  const res = await api.get("/auth/admin/users");
  return res.data;
}

export async function adminCreateUser(body) {
  const res = await api.post("/auth/admin/users", body);
  return res.data;
}

export async function adminUpdateUser(userId, body) {
  const res = await api.patch(`/auth/admin/users/${userId}`, body);
  return res.data;
}

export async function adminDeleteUser(userId) {
  await api.delete(`/auth/admin/users/${userId}`);
}

export async function fetchProjects() {
  const res = await api.get(`/projects/`);
  return res.data;
}

export async function createProject(payload) {
  const res = await api.post(`/projects/`, payload);
  return res.data;
}

export async function fetchProject(projectId) {
  const res = await api.get(`/projects/${projectId}`);
  return res.data;
}

export async function fetchTasks(projectId) {
  const res = await api.get(`/tasks/`, {
    params: { project_id: projectId }
  });
  return res.data;
}

export async function createTask(payload) {
  const res = await api.post(`/tasks/`, payload);
  return res.data;
}

export async function updateTask(taskId, payload) {
  const res = await api.patch(`/tasks/${taskId}`, payload);
  return res.data;
}

export async function deleteTask(taskId) {
  await api.delete(`/tasks/${taskId}`);
}

export async function deleteProject(projectId) {
  await api.delete(`/projects/${projectId}`);
}

export async function snapshotProjectBaseline(projectId) {
  const res = await api.post(`/projects/${projectId}/baseline/snapshot`);
  return res.data;
}

export async function updateProject(projectId, payload) {
  const res = await api.patch(`/projects/${projectId}`, payload);
  return res.data;
}

export async function fetchComments(projectId, taskId) {
  const res = await api.get(`/comments/`, {
    params: { project_id: projectId, task_id: taskId }
  });
  return res.data;
}

export async function createComment(projectId, payload) {
  const res = await api.post(`/comments/?project_id=${encodeURIComponent(projectId)}`, payload);
  return res.data;
}

export async function deleteComment(projectId, commentId) {
  await api.delete(`/comments/${commentId}`, {
    params: { project_id: projectId }
  });
}

export async function fetchAttachments(projectId, taskId) {
  const res = await api.get(`/attachments/`, {
    params: { project_id: projectId, task_id: taskId }
  });
  return res.data;
}

export async function uploadTaskAttachment(projectId, taskId, file, uploadedBy = "") {
  const fd = new FormData();
  fd.append("project_id", projectId);
  fd.append("task_id", taskId);
  fd.append("uploaded_by", uploadedBy);
  fd.append("file", file);
  const res = await api.post(`/attachments/upload`, fd, { timeout: 120000 });
  return res.data;
}

export function attachmentDownloadUrl(attachmentId, projectId) {
  return `${API_BASE}/attachments/${attachmentId}/file?project_id=${encodeURIComponent(projectId)}`;
}

export async function deleteAttachment(projectId, attachmentId) {
  await api.delete(`/attachments/${attachmentId}`, {
    params: { project_id: projectId }
  });
}

export async function fetchAlerts(projectId, unreadOnly = false) {
  const res = await api.get(`/alerts/`, {
    params: { project_id: projectId, unread_only: unreadOnly }
  });
  return res.data;
}

export async function markAlertRead(projectId, alertId, read = true) {
  const res = await api.patch(`/alerts/${alertId}`, { read }, { params: { project_id: projectId } });
  return res.data;
}

export async function createManualAlert(projectId, body) {
  const res = await api.post(`/alerts/`, body);
  return res.data;
}

export async function scanOverdueAlerts(projectId) {
  const res = await api.post(`/alerts/scan-overdue`, null, {
    params: { project_id: projectId }
  });
  return res.data;
}

export async function fetchProjectAutomations(projectId) {
  const res = await api.get(`/projects/${projectId}/automations`);
  return res.data;
}

export async function updateProjectAutomations(projectId, payload) {
  const res = await api.patch(`/projects/${projectId}/automations`, payload);
  return res.data;
}

export async function runProjectAutomations(projectId) {
  const res = await api.post(`/projects/${projectId}/automations/run`);
  return res.data;
}

export async function fetchPortfolioReport() {
  const res = await api.get(`/reports/portfolio`);
  return res.data;
}

export async function fetchProjectReport(projectId) {
  const res = await api.get(`/reports/projects/${projectId}`);
  return res.data;
}

export async function fetchProjectFormulas(projectId) {
  const res = await api.get(`/projects/${projectId}/formulas`);
  return res.data;
}

export async function updateProjectFormulas(projectId, formulas) {
  const res = await api.patch(`/projects/${projectId}/formulas`, formulas);
  return res.data;
}

export async function evaluateProjectFormulas(projectId) {
  const res = await api.post(`/projects/${projectId}/formulas/evaluate`);
  return res.data;
}

export async function fetchProjectGovernance(projectId) {
  const res = await api.get(`/projects/${projectId}/governance`);
  return res.data;
}

export async function updateProjectGovernance(projectId, payload) {
  const res = await api.patch(`/projects/${projectId}/governance`, payload);
  return res.data;
}

export async function fetchCellHistory(projectId, taskId = "", field = "", limit = 50) {
  const res = await api.get(`/projects/${projectId}/cell-history`, {
    params: {
      ...(taskId ? { task_id: taskId } : {}),
      ...(field ? { field } : {}),
      limit,
    },
  });
  return res.data;
}

export async function fetchIntegrations(projectId) {
  const res = await api.get(`/projects/${projectId}/integrations`);
  return res.data;
}

export async function updateIntegrations(projectId, integrations) {
  const res = await api.patch(`/projects/${projectId}/integrations`, { integrations });
  return res.data;
}

export async function runIntegrationTest(projectId, integrationType, eventType = "manual_test", payload = {}) {
  const res = await api.post(`/projects/${projectId}/integrations/test`, {
    integration_type: integrationType,
    event_type: eventType,
    payload,
  });
  return res.data;
}

export async function sendInboundWebhook(projectId, integrationType, payload) {
  const res = await api.post(`/projects/${projectId}/integrations/webhook/${integrationType}`, payload);
  return res.data;
}

export async function fetchIntegrationEvents(projectId, integrationType = "") {
  const res = await api.get(`/projects/${projectId}/integrations/events`, {
    params: integrationType ? { integration_type: integrationType } : {},
  });
  return res.data;
}

export async function fetchIntakeForms(projectId) {
  const res = await api.get(`/projects/${projectId}/intake-forms`);
  return res.data;
}

export async function createIntakeForm(projectId, body) {
  const res = await api.post(`/projects/${projectId}/intake-forms`, body);
  return res.data;
}

export async function patchIntakeForm(projectId, formId, body) {
  const res = await api.patch(`/projects/${projectId}/intake-forms/${formId}`, body);
  return res.data;
}

export async function deleteIntakeForm(projectId, formId) {
  await api.delete(`/projects/${projectId}/intake-forms/${formId}`);
}

export async function fetchIntakeSubmissions(projectId, formId) {
  const res = await api.get(`/projects/${projectId}/intake-forms/${formId}/submissions`);
  return res.data;
}

export async function fetchPublicIntakeForm(slug) {
  const res = await api.get(`/intake/public/${slug}`);
  return res.data;
}

export async function submitPublicIntakeForm(slug, responses) {
  const res = await api.post(`/intake/public/${slug}/submit`, { responses });
  return res.data;
}
