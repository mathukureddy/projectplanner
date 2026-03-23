import { useEffect, useMemo, useState } from "react";
import {
  fetchProjects,
  fetchIntegrations,
  updateIntegrations,
  runIntegrationTest,
  sendInboundWebhook,
  fetchIntegrationEvents,
  importJiraIssues,
} from "../api";

const INTEGRATION_TYPES = ["webhook", "slack", "email", "jira"];

function defaultIntegrations(existing) {
  const map = new Map((existing || []).map((x) => [x.type, x]));
  return INTEGRATION_TYPES.map((type) => ({
    type,
    enabled: map.get(type)?.enabled ?? false,
    endpoint: map.get(type)?.endpoint ?? "",
    secret: map.get(type)?.secret ?? "",
    settings: map.get(type)?.settings ?? {},
  }));
}

export default function IntegrationsPage() {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [integrations, setIntegrations] = useState(defaultIntegrations([]));
  const [events, setEvents] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [inboundPayload, setInboundPayload] = useState('{"event":"sync","status":"ok"}');
  const [jiraJql, setJiraJql] = useState("ORDER BY updated DESC");
  const [jiraMaxResults, setJiraMaxResults] = useState(20);

  useEffect(() => {
    (async () => {
      const list = await fetchProjects();
      setProjects(list);
      if (list.length > 0) {
        setSelectedProjectId(list[0].id || list[0]._id);
      }
    })();
  }, []);

  const selectedProject = useMemo(
    () => projects.find((p) => (p.id || p._id) === selectedProjectId),
    [projects, selectedProjectId]
  );

  useEffect(() => {
    if (!selectedProjectId) return;
    (async () => {
      const rows = await fetchIntegrations(selectedProjectId);
      setIntegrations(defaultIntegrations(rows));
      const ev = await fetchIntegrationEvents(selectedProjectId);
      setEvents(ev);
    })();
  }, [selectedProjectId]);

  const setField = (type, key, value) => {
    setIntegrations((prev) =>
      prev.map((row) => (row.type === type ? { ...row, [key]: value } : row))
    );
  };

  const setSettingField = (type, key, value) => {
    setIntegrations((prev) =>
      prev.map((row) =>
        row.type === type
          ? { ...row, settings: { ...(row.settings || {}), [key]: value } }
          : row
      )
    );
  };

  const save = async () => {
    if (!selectedProjectId) return;
    setLoading(true);
    setMessage("");
    try {
      const saved = await updateIntegrations(selectedProjectId, integrations);
      setIntegrations(defaultIntegrations(saved));
      setMessage("Integrations saved.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to save integrations.");
    } finally {
      setLoading(false);
    }
  };

  const testOne = async (type) => {
    if (!selectedProjectId) return;
    setLoading(true);
    setMessage("");
    try {
      await runIntegrationTest(selectedProjectId, type, "manual_test", {
        project: selectedProject?.name || selectedProjectId,
      });
      const ev = await fetchIntegrationEvents(selectedProjectId);
      setEvents(ev);
      setMessage(`${type} test event logged.`);
    } catch (e) {
      setMessage(e?.response?.data?.detail || `Failed to test ${type}.`);
    } finally {
      setLoading(false);
    }
  };

  const simulateInbound = async () => {
    if (!selectedProjectId) return;
    setLoading(true);
    setMessage("");
    try {
      let parsed = {};
      try {
        parsed = JSON.parse(inboundPayload || "{}");
      } catch {
        setMessage("Inbound payload must be valid JSON.");
        setLoading(false);
        return;
      }
      await sendInboundWebhook(selectedProjectId, "webhook", parsed);
      const ev = await fetchIntegrationEvents(selectedProjectId);
      setEvents(ev);
      setMessage("Inbound webhook captured.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to simulate inbound webhook.");
    } finally {
      setLoading(false);
    }
  };

  const importFromJira = async () => {
    if (!selectedProjectId) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await importJiraIssues(selectedProjectId, jiraJql, Number(jiraMaxResults));
      const ev = await fetchIntegrationEvents(selectedProjectId);
      setEvents(ev);
      setMessage(`Jira import complete. Created ${res.created}, skipped ${res.skipped}.`);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to import Jira issues.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <h2>Integrations</h2>
      <p className="muted">Configure project integrations and verify event flow.</p>

      <label>
        Project:
        <select
          value={selectedProjectId}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          style={{ marginLeft: "0.6rem" }}
        >
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Integration Configs</h3>
        {integrations.map((row) => (
          <div key={row.type} className="inline-form" style={{ marginBottom: "0.5rem" }}>
            <strong style={{ width: "80px", textTransform: "capitalize" }}>{row.type}</strong>
            <label>
              <input
                type="checkbox"
                checked={!!row.enabled}
                onChange={(e) => setField(row.type, "enabled", e.target.checked)}
              />{" "}
              Enabled
            </label>
            <input
              placeholder="Endpoint (optional)"
              value={row.endpoint || ""}
              onChange={(e) => setField(row.type, "endpoint", e.target.value)}
              style={{ minWidth: "280px" }}
            />
            <input
              placeholder="Secret (optional)"
              value={row.secret || ""}
              onChange={(e) => setField(row.type, "secret", e.target.value)}
              style={{ minWidth: "200px" }}
            />
            {row.type === "jira" ? (
              <>
                <input
                  placeholder="Jira email (settings.jira_email)"
                  value={row.settings?.jira_email || ""}
                  onChange={(e) => setSettingField("jira", "jira_email", e.target.value)}
                  style={{ minWidth: "220px" }}
                />
                <input
                  placeholder="Jira default JQL (optional)"
                  value={row.settings?.jira_jql || ""}
                  onChange={(e) => setSettingField("jira", "jira_jql", e.target.value)}
                  style={{ minWidth: "240px" }}
                />
              </>
            ) : null}
            <button type="button" onClick={() => testOne(row.type)} disabled={loading}>
              Test
            </button>
          </div>
        ))}
        <button type="button" onClick={save} disabled={loading}>
          Save Integrations
        </button>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Jira Import</h3>
        <p className="muted">
          Configure Jira integration first (type `jira`, endpoint, API token in secret, jira_email in settings), then import issues.
        </p>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <input
            placeholder="JQL"
            value={jiraJql}
            onChange={(e) => setJiraJql(e.target.value)}
            style={{ minWidth: "340px" }}
          />
          <input
            type="number"
            min={1}
            max={200}
            value={jiraMaxResults}
            onChange={(e) => setJiraMaxResults(e.target.value)}
            style={{ width: "7rem" }}
          />
          <button type="button" onClick={importFromJira} disabled={loading}>
            Import Jira Issues
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Inbound Webhook Simulator</h3>
        <textarea
          rows={4}
          value={inboundPayload}
          onChange={(e) => setInboundPayload(e.target.value)}
          style={{ width: "100%" }}
        />
        <div style={{ marginTop: "0.5rem" }}>
          <button type="button" onClick={simulateInbound} disabled={loading}>
            Send Inbound Webhook
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Integration Events</h3>
        {events.length === 0 ? (
          <p className="muted">No integration events yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Event</th>
                <th>Direction</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id}>
                  <td>{ev.integration_type}</td>
                  <td>{ev.event_type}</td>
                  <td>{ev.direction}</td>
                  <td>{new Date(ev.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {message ? <p style={{ marginTop: "0.8rem" }}>{message}</p> : null}
    </section>
  );
}

