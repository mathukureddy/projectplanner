import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000
});

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

