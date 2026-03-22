import { useEffect, useState } from "react";
import {
  fetchProjects,
  fetchIntakeForms,
  createIntakeForm,
  patchIntakeForm,
  deleteIntakeForm,
  fetchIntakeSubmissions,
} from "../api";

const PRESETS = {
  work: {
    name: "Work request",
    enabled: true,
    fields: [
      { key: "title", label: "Request title", type: "text", required: true },
      { key: "details", label: "Description", type: "textarea", required: true },
      { key: "requester", label: "Your name or team", type: "text", required: false },
    ],
    task_name_field: "title",
    task_description_field: "details",
    default_status: "Not Started",
  },
  change: {
    name: "Change request",
    enabled: true,
    fields: [
      { key: "title", label: "Change title", type: "text", required: true },
      { key: "details", label: "Business justification", type: "textarea", required: true },
      { key: "needed_by", label: "Needed by", type: "date", required: false },
    ],
    task_name_field: "title",
    task_description_field: "details",
    task_end_date_field: "needed_by",
    default_status: "Not Started",
  },
  bug: {
    name: "Bug / issue intake",
    enabled: true,
    fields: [
      { key: "title", label: "Summary", type: "text", required: true },
      { key: "details", label: "Steps to reproduce", type: "textarea", required: true },
    ],
    task_name_field: "title",
    task_description_field: "details",
    default_status: "Not Started",
  },
};

export default function IntakeFormsPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [forms, setForms] = useState([]);
  const [presetKey, setPresetKey] = useState("work");
  const [message, setMessage] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [subs, setSubs] = useState({});

  useEffect(() => {
    (async () => {
      const list = await fetchProjects();
      setProjects(list);
      if (list.length) setProjectId(list[0].id || list[0]._id);
    })();
  }, []);

  const loadForms = async (pid) => {
    if (!pid) return;
    setMessage("");
    try {
      const data = await fetchIntakeForms(pid);
      setForms(data);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to load forms.");
    }
  };

  useEffect(() => {
    loadForms(projectId);
  }, [projectId]);

  const publicUrl = (slug) => `${window.location.origin}/intake/${slug}`;

  const copyLink = (slug) => {
    navigator.clipboard.writeText(publicUrl(slug));
    setMessage("Public link copied to clipboard.");
  };

  const handleCreatePreset = async () => {
    if (!projectId) return;
    setMessage("");
    try {
      const body = PRESETS[presetKey];
      await createIntakeForm(projectId, body);
      await loadForms(projectId);
      setMessage("Form created.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Create failed.");
    }
  };

  const toggleEnabled = async (form) => {
    try {
      await patchIntakeForm(projectId, form.id, { enabled: !form.enabled });
      await loadForms(projectId);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Update failed.");
    }
  };

  const handleDelete = async (form) => {
    if (!window.confirm(`Delete form "${form.name}"?`)) return;
    try {
      await deleteIntakeForm(projectId, form.id);
      await loadForms(projectId);
      setMessage("Form deleted.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Delete failed.");
    }
  };

  const loadSubs = async (form) => {
    if (expanded === form.id) {
      setExpanded(null);
      return;
    }
    setExpanded(form.id);
    try {
      const rows = await fetchIntakeSubmissions(projectId, form.id);
      setSubs((prev) => ({ ...prev, [form.id]: rows }));
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to load submissions.");
    }
  };

  return (
    <section>
      <h2>Intake forms</h2>
      <p className="muted">
        Build shareable forms; each submission creates a <strong>new task</strong> in the selected project.
        Public link format: <code>/intake/&lt;slug&gt;</code> (no sign-in).
      </p>

      <label>
        Project:{" "}
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Create from template</h3>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <select value={presetKey} onChange={(e) => setPresetKey(e.target.value)}>
            <option value="work">Work request</option>
            <option value="change">Change request</option>
            <option value="bug">Bug / issue</option>
          </select>
          <button type="button" onClick={handleCreatePreset} disabled={!projectId}>
            Create form
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Forms for this project</h3>
        {forms.length === 0 ? (
          <p className="muted">No intake forms yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Enabled</th>
                <th>Public link</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {forms.map((f) => (
                <tr key={f.id}>
                  <td>{f.name}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!f.enabled}
                      onChange={() => toggleEnabled(f)}
                      title="Toggle enabled"
                    />
                  </td>
                  <td>
                    <code style={{ fontSize: "0.8rem" }}>{publicUrl(f.slug)}</code>
                    <div className="inline-form" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                      <button type="button" onClick={() => copyLink(f.slug)}>
                        Copy link
                      </button>
                      <a href={`/intake/${f.slug}`} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    </div>
                  </td>
                  <td>
                    <div className="inline-form" style={{ marginBottom: 0 }}>
                      <button type="button" onClick={() => loadSubs(f)}>
                        {expanded === f.id ? "Hide submissions" : "Submissions"}
                      </button>
                      <button type="button" onClick={() => handleDelete(f)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {expanded ? (
          <div style={{ marginTop: "1rem" }}>
            <h4>Recent submissions</h4>
            {(subs[expanded] || []).length === 0 ? (
              <p className="muted">None yet.</p>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Task id</th>
                    <th>Responses (summary)</th>
                  </tr>
                </thead>
                <tbody>
                  {(subs[expanded] || []).map((s) => (
                    <tr key={s.id}>
                      <td>{new Date(s.submitted_at).toLocaleString()}</td>
                      <td>
                        <code>{s.task_id}</code>
                      </td>
                      <td style={{ maxWidth: "20rem", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {JSON.stringify(s.responses)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </div>

      {message ? <p style={{ marginTop: "0.75rem" }}>{message}</p> : null}
    </section>
  );
}
