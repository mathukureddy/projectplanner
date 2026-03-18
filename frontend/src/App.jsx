import { Routes, Route, Link } from "react-router-dom";
import ProjectsPage from "./pages/ProjectsPage.jsx";
import ProjectDetailPage from "./pages/ProjectDetailPage.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>ProjectPlanning</h1>
        <nav>
          <Link to="/">Projects</Link>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

