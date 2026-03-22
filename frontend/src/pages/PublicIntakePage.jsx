import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchPublicIntakeForm, submitPublicIntakeForm, API_BASE } from "../api";

export default function PublicIntakePage() {
  const { slug } = useParams();
  const [schema, setSchema] = useState(null);
  const [responses, setResponses] = useState({});
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setError("");
      setLoading(true);
      try {
        const data = await fetchPublicIntakeForm(slug);
        setSchema(data);
        const init = {};
        for (const f of data.fields || []) {
          init[f.key] = "";
        }
        setResponses(init);
      } catch (e) {
        setError(e?.response?.data?.detail || "Form not found or is disabled.");
      } finally {
        setLoading(false);
      }
    })();
  }, [slug]);

  const setVal = (key, v) => setResponses((prev) => ({ ...prev, [key]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const result = await submitPublicIntakeForm(slug, responses);
      setDone(result);
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Submission failed.");
    }
  };

  if (loading) {
    return (
      <div className="login-shell">
        <p>Loading form…</p>
      </div>
    );
  }

  if (error && !schema) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <h2>Intake form</h2>
          <p style={{ color: "#b91c1c" }}>{error}</p>
          <p className="muted">
            API: <code>{API_BASE}</code>
          </p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <h2>Thank you</h2>
          <p>{done.message}</p>
          <p className="muted">You can close this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-shell">
      <form className="login-card" style={{ maxWidth: "520px" }} onSubmit={handleSubmit}>
        <h2>{schema.name}</h2>
        <p className="muted">Project: {schema.project_name}</p>
        {(schema.fields || []).map((f) => (
          <label key={f.key} style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <span>
              {f.label}
              {f.required ? " *" : ""}
            </span>
            {f.type === "textarea" ? (
              <textarea
                required={!!f.required}
                value={responses[f.key] ?? ""}
                onChange={(e) => setVal(f.key, e.target.value)}
                rows={4}
              />
            ) : f.type === "date" ? (
              <input
                type="date"
                required={!!f.required}
                value={responses[f.key] ?? ""}
                onChange={(e) => setVal(f.key, e.target.value)}
              />
            ) : f.type === "number" ? (
              <input
                type="number"
                required={!!f.required}
                value={responses[f.key] ?? ""}
                onChange={(e) => setVal(f.key, e.target.value)}
              />
            ) : (
              <input
                type={f.type === "email" ? "email" : "text"}
                required={!!f.required}
                value={responses[f.key] ?? ""}
                onChange={(e) => setVal(f.key, e.target.value)}
              />
            )}
          </label>
        ))}
        {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
        <button type="submit">Submit request</button>
        <p className="muted" style={{ marginTop: "0.75rem" }}>
          <Link to="/">App home</Link> (sign-in required)
        </p>
      </form>
    </div>
  );
}
