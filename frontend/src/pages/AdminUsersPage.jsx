import { useEffect, useState } from "react";
import { fetchAdminUsers, adminCreateUser, adminUpdateUser, adminDeleteUser } from "../api";

export default function AdminUsersPage({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    role: "editor",
  });
  const [rowEdits, setRowEdits] = useState({});

  const load = async () => {
    setMessage("");
    setLoading(true);
    try {
      const data = await fetchAdminUsers();
      setUsers(data);
      const edits = {};
      for (const u of data) {
        edits[u.id] = {
          email: u.email || "",
          role: u.role,
          newPassword: "",
        };
      }
      setRowEdits(edits);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setMessage("");
    try {
      const body = {
        username: newUser.username.trim(),
        password: newUser.password,
        role: newUser.role,
      };
      if (newUser.email.trim()) body.email = newUser.email.trim();
      await adminCreateUser(body);
      setNewUser({ username: "", email: "", password: "", role: "editor" });
      await load();
      setMessage("User created.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Create failed.");
    }
  };

  const handleSaveRow = async (userId) => {
    setMessage("");
    const ed = rowEdits[userId];
    if (!ed) return;
    try {
      const body = { role: ed.role };
      if (ed.email !== undefined) body.email = ed.email.trim() || null;
      if (ed.newPassword && ed.newPassword.length >= 6) body.password = ed.newPassword;
      await adminUpdateUser(userId, body);
      await load();
      setMessage("User updated.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Update failed.");
    }
  };

  const handleDelete = async (userId, username) => {
    if (!window.confirm(`Delete user "${username}"?`)) return;
    setMessage("");
    try {
      await adminDeleteUser(userId);
      await load();
      setMessage("User deleted.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Delete failed.");
    }
  };

  const setEdit = (userId, patch) => {
    setRowEdits((prev) => ({
      ...prev,
      [userId]: { ...prev[userId], ...patch },
    }));
  };

  if (String(currentUser?.role || "").toLowerCase() !== "admin") {
    return (
      <section>
        <h2>Users</h2>
        <p>Admin access is required to manage users.</p>
      </section>
    );
  }

  return (
    <section>
      <h2>User management</h2>
      <p className="muted">Create and maintain database users (roles: viewer, editor, admin).</p>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Add user</h3>
        <form className="inline-form" style={{ flexWrap: "wrap" }} onSubmit={handleCreate}>
          <input
            placeholder="Username"
            value={newUser.username}
            onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
            required
          />
          <input
            type="email"
            placeholder="Email (optional)"
            value={newUser.email}
            onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
          />
          <input
            type="password"
            placeholder="Password (min 6)"
            value={newUser.password}
            onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
            required
            minLength={6}
          />
          <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
            <option value="viewer">viewer</option>
            <option value="editor">editor</option>
            <option value="admin">admin</option>
          </select>
          <button type="submit">Create user</button>
        </form>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Users</h3>
        {loading ? (
          <p>Loading…</p>
        ) : users.length === 0 ? (
          <p className="muted">No database users yet. Bootstrap admin (env) is not listed here.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>New password</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const ed = rowEdits[u.id] || { email: u.email || "", role: u.role, newPassword: "" };
                return (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>
                      <input
                        value={ed.email}
                        onChange={(e) => setEdit(u.id, { email: e.target.value })}
                        placeholder="email"
                        style={{ minWidth: "10rem" }}
                      />
                    </td>
                    <td>
                      <select value={ed.role} onChange={(e) => setEdit(u.id, { role: e.target.value })}>
                        <option value="viewer">viewer</option>
                        <option value="editor">editor</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>
                      <input
                        type="password"
                        placeholder="optional"
                        value={ed.newPassword}
                        onChange={(e) => setEdit(u.id, { newPassword: e.target.value })}
                        style={{ minWidth: "8rem" }}
                      />
                    </td>
                    <td>
                      <div className="inline-form" style={{ marginBottom: 0 }}>
                        <button type="button" onClick={() => handleSaveRow(u.id)}>
                          Save
                        </button>
                        <button type="button" onClick={() => handleDelete(u.id, u.username)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {message ? <p style={{ marginTop: "0.75rem" }}>{message}</p> : null}
    </section>
  );
}
