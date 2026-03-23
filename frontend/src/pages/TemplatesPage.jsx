import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchTemplateCatalog,
  fetchTemplateSolutionSets,
  createProjectFromTemplate,
  createProjectsFromSolutionSet,
} from "../api";

export default function TemplatesPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState([]);
  const [solutionSets, setSolutionSets] = useState([]);
  const [namePrefix, setNamePrefix] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      const [c, s] = await Promise.all([fetchTemplateCatalog(), fetchTemplateSolutionSets()]);
      setCatalog(c);
      setSolutionSets(s);
    })();
  }, []);

  const createFromTemplate = async (template) => {
    const name = window.prompt("Project name", `${template.name} - ${new Date().toISOString().slice(0, 10)}`);
    if (!name || !name.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await createProjectFromTemplate(template.id, name.trim());
      setMessage(`Created: ${res.project.name}`);
      navigate(`/projects/${res.project.id}`);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to create project.");
    } finally {
      setLoading(false);
    }
  };

  const createFromSolutionSet = async (sset) => {
    if (!namePrefix.trim()) {
      setMessage("Enter a prefix for solution-set project names.");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const res = await createProjectsFromSolutionSet(sset.id, namePrefix.trim());
      setMessage(`Created ${res.created_projects.length} projects from "${sset.name}".`);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to create solution set projects.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <h2>Templates & Solution Sets</h2>
      <p className="muted">
        Create projects quickly from pre-built templates (Project Plan, Agile, PMO, Marketing, IT intake).
      </p>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Template catalog</h3>
        {catalog.length === 0 ? (
          <p className="muted">No templates found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Description</th>
                <th>Tasks</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {catalog.map((t) => (
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td>{t.category}</td>
                  <td>{t.description}</td>
                  <td>{t.task_count}</td>
                  <td>
                    <button type="button" disabled={loading} onClick={() => createFromTemplate(t)}>
                      Use template
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Solution sets</h3>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <input
            placeholder="Project name prefix (required)"
            value={namePrefix}
            onChange={(e) => setNamePrefix(e.target.value)}
          />
        </div>
        {solutionSets.length === 0 ? (
          <p className="muted">No solution sets found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Templates</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {solutionSets.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.description}</td>
                  <td>{(s.template_ids || []).join(", ")}</td>
                  <td>
                    <button type="button" disabled={loading} onClick={() => createFromSolutionSet(s)}>
                      Create set projects
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {message ? <p style={{ marginTop: "0.75rem" }}>{message}</p> : null}
    </section>
  );
}

