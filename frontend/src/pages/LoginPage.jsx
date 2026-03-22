import { useState } from "react";
import { login } from "../api";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(username.trim(), password);
      localStorage.setItem("pp_auth_token", result.access_token);
      localStorage.setItem("pp_auth_user", JSON.stringify(result.user || {}));
      onLogin(result.user || null);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((x) => x.msg || JSON.stringify(x)).join("; "));
      } else if (typeof detail === "string") {
        setError(detail);
      } else if (err?.message === "Network Error" || err?.code === "ERR_NETWORK") {
        setError("Cannot reach API. Is the backend running and VITE_API_BASE correct?");
      } else {
        setError("Login failed.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={handleSubmit}>
        <h2>ProjectPlanner Login</h2>
        <p className="muted">Sign in to continue.</p>
        <input
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Login"}
        </button>
        <p className="muted" style={{ marginTop: "0.6rem" }}>
          Default admin: <code>admin / admin123</code>
        </p>
        {error ? <p style={{ color: "#b91c1c" }}>{error}</p> : null}
      </form>
    </div>
  );
}

