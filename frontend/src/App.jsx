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
import AdminUsersPage from "./pages/AdminUsersPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { fetchMe } from "./api";

export default function App() {
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState(null);

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
            <NavLink to="/alerts-center">Alerts</NavLink>
            <NavLink to="/sharing-permissions">Sharing & Permissions</NavLink>
            <NavLink to="/integrations">Integrations</NavLink>
          </div>
          <NavLink to="/dashboard">Dashboard</NavLink>
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
          <Route path="/admin/users" element={<AdminUsersPage currentUser={user} />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

