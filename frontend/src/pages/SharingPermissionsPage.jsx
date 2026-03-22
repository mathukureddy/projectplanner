import { useEffect, useState } from "react";
import { fetchProjects, fetchProject, updateProject } from "../api.js";

export default function SharingPermissionsPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");

  useEffect(() => {
    (async () => {
      const p = await fetchProjects();
      setProjects(p);
      if (p.length > 0) setProjectId(p[0].id || p[0]._id);
    })();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => setProject(await fetchProject(projectId)))();
  }, [projectId]);

  async function addShare(e) {
    e.preventDefault();
    if (!project || !email.trim()) return;
    const shares = [...(project.shares || []), { email: email.trim(), role }];
    const p = await updateProject(projectId, { shares });
    setProject(p);
    setEmail("");
    setRole("viewer");
  }

  async function removeShare(targetEmail) {
    if (!project) return;
    const shares = (project.shares || []).filter((s) => s.email !== targetEmail);
    const p = await updateProject(projectId, { shares });
    setProject(p);
  }

  return (
    <div>
      <h2>Sharing & Permissions</h2>
      <div className="inline-form">
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>{p.name}</option>
          ))}
        </select>
      </div>

      <form onSubmit={addShare} className="inline-form">
        <input
          type="email"
          placeholder="user@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="viewer">Viewer</option>
          <option value="editor">Editor</option>
          <option value="admin">Admin</option>
        </select>
        <button type="submit">Add share</button>
      </form>

      <table className="data-table">
        <thead>
          <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {!project || (project.shares || []).length === 0 ? (
            <tr>
              <td colSpan={3}>No shares</td>
            </tr>
          ) : (
            (project.shares || []).map((s) => (
              <tr key={s.email}>
                <td>{s.email}</td>
                <td>{s.role}</td>
                <td>
                  <button type="button" onClick={() => removeShare(s.email)}>Remove</button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

