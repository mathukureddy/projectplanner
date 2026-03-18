import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function fetchProjects() {
  const res = await axios.get(`${API_BASE}/projects/`);
  return res.data;
}

export async function createProject(payload) {
  const res = await axios.post(`${API_BASE}/projects/`, payload);
  return res.data;
}

export async function fetchProject(projectId) {
  const res = await axios.get(`${API_BASE}/projects/${projectId}`);
  return res.data;
}

export async function fetchTasks(projectId) {
  const res = await axios.get(`${API_BASE}/tasks/`, {
    params: { project_id: projectId }
  });
  return res.data;
}

export async function createTask(payload) {
  const res = await axios.post(`${API_BASE}/tasks/`, payload);
  return res.data;
}

