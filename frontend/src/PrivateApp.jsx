import { useEffect, useState } from "react";
import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import ProjectsPage from "./pages/ProjectsPage.jsx";
import ProjectDetailPage from "./pages/ProjectDetailPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AutomationRulesPage from "./pages/AutomationRulesPage.jsx";
import DataFormulasPage from "./pages/DataFormulasPage.jsx";
import AlertsPage from "./pages/AlertsPage.jsx";
import SharingPermissionsPage from "./pages/SharingPermissionsPage.jsx";
import IntegrationsPage from "./pages/IntegrationsPage.jsx";
import IntakeFormsPage from "./pages/IntakeFormsPage.jsx";
import WorkloadPage from "./pages/WorkloadPage.jsx";
import TemplatesPage from "./pages/TemplatesPage.jsx";
import AdminUsersPage from "./pages/AdminUsersPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { fetchInboxAlerts, fetchMe } from "./api";

export default function PrivateApp() {
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [unreadInboxCount, setUnreadInboxCount] = useState(0);

  useEffect(() => {
    (async () => {
      const token = localStorage.getItem("pp_auth_token");
      if (!token) {
        setAuthLoading(false);
        return;
      }
      try {
        const me = await fetchMe();
        setUser(me);
      } catch {
        localStorage.removeItem("pp_auth_token");
        localStorage.removeItem("pp_auth_user");
      } finally {
        setAuthLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!user?.username) {
      setUnreadInboxCount(0);
      return;
    }
    let active = true;
    const loadUnread = async () => {
      try {
        const alerts = await fetchInboxAlerts(user.username, true);
        if (active) setUnreadInboxCount(Array.isArray(alerts) ? alerts.length : 0);
      } catch {
        if (active) setUnreadInboxCount(0);
      }
    };
    loadUnread();
    const t = setInterval(loadUnread, 30000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [user?.username]);

  const handleLogout = () => {
    localStorage.removeItem("pp_auth_token");
    localStorage.removeItem("pp_auth_user");
    setUser(null);
  };

  if (authLoading) return <div style={{ padding: "1rem" }}>Loading...</div>;
  if (!user) return <LoginPage onLogin={setUser} />;

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <h1>ProjectPlanner</h1>
        <p className="muted" style={{ margin: "0 0 0.8rem 0" }}>
          {user.username} ({user.role})
        </p>
        <nav>
          <NavLink to="/">Projects</NavLink>
          <div className="side-submenu">
            <NavLink to="/automation-rules">Automation Rules</NavLink>
            <NavLink to="/data-formulas">Data Formulas</NavLink>
            <NavLink to="/alerts-center">
              Alerts
              {unreadInboxCount > 0 ? (
                <span
                  style={{
                    marginLeft: "0.45rem",
                    background: "#ef4444",
                    color: "#fff",
                    borderRadius: "999px",
                    padding: "0.05rem 0.45rem",
                    fontSize: "0.74rem",
                    fontWeight: 700,
                    verticalAlign: "middle",
                  }}
                >
                  {unreadInboxCount}
                </span>
              ) : null}
            </NavLink>
            <NavLink to="/sharing-permissions">Sharing & Permissions</NavLink>
            <NavLink to="/integrations">Integrations</NavLink>
            <NavLink to="/intake-forms">Intake forms</NavLink>
            <NavLink to="/templates">Templates</NavLink>
          </div>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/workload">Workload</NavLink>
          {String(user.role || "").toLowerCase() === "admin" ? (
            <NavLink to="/admin/users">Users (admin)</NavLink>
          ) : null}
          <button type="button" onClick={handleLogout} style={{ marginTop: "0.5rem" }}>
            Logout
          </button>
        </nav>
      </aside>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/automation-rules" element={<AutomationRulesPage />} />
          <Route path="/data-formulas" element={<DataFormulasPage />} />
          <Route path="/alerts-center" element={<AlertsPage />} />
          <Route path="/sharing-permissions" element={<SharingPermissionsPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/intake-forms" element={<IntakeFormsPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/workload" element={<WorkloadPage />} />
          <Route path="/admin/users" element={<AdminUsersPage currentUser={user} />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
