import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";

const TABS = ["Dashboard", "Documents", "Users", "Audit Logs"];

export default function Admin() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [stats, setStats] = useState({});
  const [file, setFile] = useState(null);
  const [uploadMeta, setUploadMeta] = useState({ department: "", semester: "", subject: "" });
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [documents, setDocuments] = useState([]);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [scrapeMsg, setScrapeMsg] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [bulkDeletingDocs, setBulkDeletingDocs] = useState(false);

  // â”€â”€ Fetch helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const fetchStats = async () => {
    try {
      const res = await API.get("/admin/stats");
      setStats(res.data);
    } catch { }
  };

  const fetchDocuments = async () => {
    try {
      const res = await API.get("/admin/documents?page=1&page_size=50");
      const docs = res.data.documents ?? res.data ?? [];
      setDocuments(docs);
      setSelectedDocIds((prev) => prev.filter((id) => docs.some((d) => d.id === id)));
    } catch { }
  };

  const fetchUsers = async () => {
    try {
      const res = await API.get("/admin/users?page=1&page_size=50");
      setUsers(res.data.users ?? res.data ?? []);
    } catch { }
  };

  const fetchAuditLogs = async () => {
    try {
      const res = await API.get("/admin/audit-logs?page=1&page_size=50");
      setAuditLogs(res.data.logs ?? []);
    } catch { }
  };

  useEffect(() => {
    fetchStats();
    fetchDocuments();
    fetchUsers();
    fetchAuditLogs();
  }, []);

  // â”€â”€ Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const deleteUser = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try {
      await API.delete(`/admin/users/${id}`);
      fetchUsers();
      fetchStats();
    } catch (err) {
      alert(err.response?.data?.detail || "Delete failed");
    }
  };

  const toggleRole = async (id, currentRole) => {
    try {
      await API.put(`/admin/users/${id}/role`, {
        role: currentRole === "admin" ? "student" : "admin",
      });
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Role update failed");
    }
  };

  const toggleStatus = async (id, isActive) => {
    try {
      await API.put(`/admin/users/${id}/status`, { is_active: !isActive });
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Status update failed");
    }
  };

  const deleteDocument = async (id) => {
    if (!window.confirm("Delete this document and all its chunks?")) return;
    try {
      await API.delete(`/admin/documents/${id}`);
      setSelectedDocIds((prev) => prev.filter((x) => x !== id));
      fetchDocuments();
      fetchStats();
    } catch (err) {
      alert(err.response?.data?.detail || "Delete failed");
    }
  };

  const toggleDocumentSelection = (id) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAllDocuments = () => {
    const ids = documents.map((d) => d.id);
    setSelectedDocIds((prev) => (prev.length === ids.length ? [] : ids));
  };

  const deleteSelectedDocuments = async () => {
    if (!selectedDocIds.length || bulkDeletingDocs) return;
    if (!window.confirm(`Delete ${selectedDocIds.length} selected documents and all their chunks?`)) return;

    setBulkDeletingDocs(true);
    try {
      const ids = [...selectedDocIds];
      const results = await Promise.allSettled(
        ids.map((id) => API.delete(`/admin/documents/${id}`))
      );
      const ok = results.filter((r) => r.status === "fulfilled").length;
      const failed = results.length - ok;
      setSelectedDocIds([]);
      await fetchDocuments();
      await fetchStats();
      if (failed > 0) {
        alert(`Deleted ${ok} document(s). Failed to delete ${failed} document(s).`);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "Bulk delete failed");
    } finally {
      setBulkDeletingDocs(false);
    }
  };

  const reindexDocument = async (id) => {
    if (!window.confirm("Re-parse and reindex this result PDF?")) return;
    try {
      const res = await API.post(`/document/reindex/${id}`);
      alert(`✅ Reindexed! ${res.data.students_found} students, ${res.data.chunks_created} chunks.`);
      fetchStats();
      fetchDocuments();
    } catch (err) {
      alert(err.response?.data?.detail || "Reindex failed");
    }
  };

  const handleUpload = async () => {
    if (!file) { alert("Select a file"); return; }
    const formData = new FormData();
    formData.append("file", file);
    if (uploadMeta.department) formData.append("department", uploadMeta.department);
    if (uploadMeta.semester) formData.append("semester", uploadMeta.semester);
    if (uploadMeta.subject) formData.append("subject", uploadMeta.subject);

    setLoading(true);
    try {
      const res = await API.post("/document/upload", formData);
      alert(`✅ Uploaded! ${res.data.chunks_created} chunks indexed.\nLabel: ${res.data.source_label || "auto"}`);
      setFile(null);
      setUploadMeta({ department: "", semester: "", subject: "" });
      fetchStats();
      fetchDocuments();
    } catch (err) {
      alert(err.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleScrapeUrl = async () => {
    if (!scrapeUrl.trim()) { alert("Enter a URL"); return; }

    // Strip URL fragment (#section) â€” fragments are client-side only
    const cleanUrl = scrapeUrl.split("#")[0].trim();
    if (!cleanUrl.startsWith("http")) {
      alert("URL must start with http:// or https://");
      return;
    }

    setLoading(true);
    setScrapeMsg("Scraping... this may take a moment.");
    try {
      const res = await API.post(`/document/scrape?url=${encodeURIComponent(cleanUrl)}`);
      setScrapeMsg(`✅ Scraped! Label: ${res.data.source_label || "auto"}`);
      setScrapeUrl("");
      fetchStats();
      fetchDocuments();
    } catch (err) {
      setScrapeMsg(`❌ ${err.response?.data?.detail || "Scraping failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleScrapeAll = async () => {
    setLoading(true);
    setScrapeMsg("Running all saved sources...");
    try {
      const res = await API.post("/admin/scrape", {});
      setScrapeMsg(`✅ Done! ${res.data.total_chunks_indexed} chunks indexed.`);
      fetchStats();
      fetchDocuments();
    } catch (err) {
      setScrapeMsg(`❌ ${err.response?.data?.detail || "Scraping failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    navigate("/login");
  };

  // â”€â”€ Render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  return (
    <div className="min-h-screen flex bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 relative overflow-hidden">
      <div className="absolute w-[600px] h-[600px] bg-blue-500 opacity-5 rounded-full blur-3xl top-0 left-0 pointer-events-none" />
      <div className="absolute w-[400px] h-[400px] bg-indigo-400 opacity-5 rounded-full blur-3xl bottom-0 right-0 pointer-events-none" />

      {/* â”€â”€ Sidebar â”€â”€ */}
      <div className={`${sidebarOpen ? "w-64" : "w-16"} transition-all duration-300 bg-white/5 border-r border-white/10 backdrop-blur-xl flex flex-col shrink-0`}>
        <div className="flex justify-between items-center px-4 pt-5 pb-4 border-b border-white/10">
          {sidebarOpen && <span className="text-white font-bold text-sm tracking-wide">COLLEGE AI</span>}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-8 h-8 rounded-lg bg-white/10 text-white flex items-center justify-center hover:bg-white/20 transition ml-auto"
          >
            {sidebarOpen ? "‹" : "›"}
          </button>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                activeTab === tab
                  ? "bg-blue-500/30 text-blue-200 border border-blue-400/30"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              }`}
            >
              <span className="text-base">{tabIcon(tab)}</span>
              {sidebarOpen && <span>{tab}</span>}
            </button>
          ))}
          <hr className="border-white/10 my-2" />
          <button
            onClick={() => navigate("/chat")}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-white/60 hover:text-white hover:bg-white/10 transition"
          >
            <span>💬</span>
            {sidebarOpen && <span>Chat</span>}
          </button>
        </nav>

        <div className="px-2 pb-4">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 hover:text-red-300 transition"
          >
            <span>⎋</span>
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </div>

      {/* â”€â”€ Main Content â”€â”€ */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-white">{activeTab}</h1>
            <p className="text-white/50 text-sm mt-1">Admin Panel · Saraswati College</p>
          </div>

          {/* â”€â”€ Dashboard Tab â”€â”€ */}
          {activeTab === "Dashboard" && (
            <div className="space-y-8">
              {/* Stats */}
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <StatCard label="Total Users"     value={stats.users}          icon="👥" color="blue"   />
                <StatCard label="Active Users"    value={stats.active_users}   icon="✅" color="green"  />
                <StatCard label="Documents"       value={stats.documents}      icon="📄" color="indigo" />
                <StatCard label="Chunks Indexed"  value={stats.chunks}         icon="🧩" color="purple" />
                <StatCard label="Chat Sessions"   value={stats.chat_sessions}  icon="💬" color="cyan"   />
                <StatCard label="Scrape Sources"  value={stats.scrape_sources} icon="🌐" color="orange" />
              </div>

              {/* Upload */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                <h2 className="text-white font-semibold mb-5 flex items-center gap-2">
                  <span>📤</span> Upload Document
                </h2>
                <p className="text-white/40 text-xs mb-4">
                  Department, label and content type are auto-detected from filename.
                </p>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <input
                    placeholder="Department (optional)"
                    value={uploadMeta.department}
                    onChange={(e) => setUploadMeta({ ...uploadMeta, department: e.target.value })}
                    className="bg-white/10 border border-white/20 text-white placeholder-white/30 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400"
                  />
                  <input
                    placeholder="Semester (optional)"
                    type="number"
                    value={uploadMeta.semester}
                    onChange={(e) => setUploadMeta({ ...uploadMeta, semester: e.target.value })}
                    className="bg-white/10 border border-white/20 text-white placeholder-white/30 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400"
                  />
                  <input
                    placeholder="Subject (optional)"
                    value={uploadMeta.subject}
                    onChange={(e) => setUploadMeta({ ...uploadMeta, subject: e.target.value })}
                    className="bg-white/10 border border-white/20 text-white placeholder-white/30 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400"
                  />
                </div>
                <div className="flex items-center gap-4 mb-4">
                  <label className="cursor-pointer bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl text-sm font-medium transition">
                    Choose File
                    <input type="file" onChange={(e) => setFile(e.target.files[0])} className="hidden" />
                  </label>
                  <span className="text-white/50 text-sm">{file ? file.name : "No file selected"}</span>
                </div>
                <button
                  onClick={handleUpload}
                  disabled={loading || !file}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition"
                >
                  {loading ? "Uploading..." : "Upload & Index"}
                </button>
              </div>

              {/* Scrape */}
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                <h2 className="text-white font-semibold mb-2 flex items-center gap-2">
                  <span>🌐</span> Web Scraper
                </h2>
                <p className="text-white/40 text-xs mb-5">
                  URL fragments (#section) are automatically removed. Labels are auto-detected from URL.
                </p>

                <div className="flex gap-3 mb-3">
                  <input
                    placeholder="https://engineering.saraswatikharghar.edu.in/faculty-cse-data-science/"
                    value={scrapeUrl}
                    onChange={(e) => setScrapeUrl(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !loading && handleScrapeUrl()}
                    className="flex-1 bg-white/10 border border-white/20 text-white placeholder-white/30 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400"
                  />
                  <button
                    onClick={handleScrapeUrl}
                    disabled={loading}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition whitespace-nowrap"
                  >
                    {loading ? "Scraping..." : "Scrape URL"}
                  </button>
                </div>

                {scrapeMsg && (
                  <p className={`text-sm mb-3 px-1 ${
                    scrapeMsg.startsWith("✅") ? "text-green-400" :
                    scrapeMsg.startsWith("❌") ? "text-red-400" : "text-white/50"
                  }`}>
                    {scrapeMsg}
                  </p>
                )}

                <button
                  onClick={handleScrapeAll}
                  disabled={loading}
                  className="bg-white/10 hover:bg-white/20 disabled:opacity-40 text-white/80 px-6 py-2.5 rounded-xl text-sm font-medium transition border border-white/20"
                >
                  {loading ? "Running..." : "Run All Saved Sources"}
                </button>
              </div>
            </div>
          )}

          {/* â”€â”€ Documents Tab â”€â”€ */}
          {activeTab === "Documents" && (
            <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm">
              <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between gap-3">
                <div className="flex items-center gap-4">
                  <span className="text-white font-medium">{documents.length} documents indexed</span>
                  {documents.length > 0 && (
                    <label className="inline-flex items-center gap-2 text-xs text-white/70">
                      <input
                        type="checkbox"
                        checked={selectedDocIds.length > 0 && selectedDocIds.length === documents.length}
                        onChange={toggleSelectAllDocuments}
                        className="w-4 h-4 accent-blue-500"
                      />
                      Select all
                    </label>
                  )}
                </div>
                <button
                  onClick={deleteSelectedDocuments}
                  disabled={!selectedDocIds.length || bulkDeletingDocs}
                  className="text-xs px-3 py-1.5 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  {bulkDeletingDocs ? "Deleting..." : `Delete Selected${selectedDocIds.length ? ` (${selectedDocIds.length})` : ""}`}
                </button>
              </div>
              <div className="divide-y divide-white/5">
                {documents.length === 0 && (
                  <p className="text-white/40 text-sm px-6 py-8 text-center">No documents yet.</p>
                )}
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between px-6 py-4 hover:bg-white/5 transition">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selectedDocIds.includes(doc.id)}
                        onChange={() => toggleDocumentSelection(doc.id)}
                        className="mt-1 w-4 h-4 accent-blue-500"
                      />
                      <div>
                      <p className="text-white text-sm font-medium truncate max-w-md">
                        {doc.source_label || doc.filename}
                      </p>
                      <p className="text-white/40 text-xs mt-0.5">
                        {doc.dept_tag || doc.department} · {doc.file_type?.toUpperCase()} ·
                        <span className="ml-1 truncate">{doc.filename.length > 50 ? doc.filename.slice(0, 50) + "…" : doc.filename}</span>
                      </p>
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      {doc.file_type === "pdf" && (
                        <button
                          onClick={() => reindexDocument(doc.id)}
                          className="text-xs px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 transition whitespace-nowrap"
                        >
                          Reindex
                        </button>
                      )}
                      <button
                        onClick={() => deleteDocument(doc.id)}
                        className="text-red-400 hover:text-red-300 text-sm px-3 py-1.5 rounded-lg hover:bg-red-500/10 transition"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* â”€â”€ Users Tab â”€â”€ */}
          {activeTab === "Users" && (
            <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm">
              <div className="px-6 py-4 border-b border-white/10">
                <span className="text-white font-medium">{users.length} registered users</span>
              </div>
              <div className="divide-y divide-white/5">
                {users.length === 0 && (
                  <p className="text-white/40 text-sm px-6 py-8 text-center">No users found.</p>
                )}
                {users.map((u) => (
                  <div key={u.id} className="flex items-center justify-between px-6 py-4 hover:bg-white/5 transition">
                    <div>
                      <p className="text-white text-sm font-medium">{u.email}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          u.role === "admin" ? "bg-purple-500/20 text-purple-300" : "bg-blue-500/20 text-blue-300"
                        }`}>{u.role}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          u.is_active ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
                        }`}>{u.is_active ? "active" : "inactive"}</span>
                        <span className="text-white/30 text-xs">{u.department}</span>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => toggleRole(u.id, u.role)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 transition">
                        {u.role === "admin" ? "Demote" : "Promote"}
                      </button>
                      <button onClick={() => toggleStatus(u.id, u.is_active)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30 transition">
                        {u.is_active ? "Disable" : "Enable"}
                      </button>
                      <button onClick={() => deleteUser(u.id)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-red-500/20 text-red-300 hover:bg-red-500/30 transition">
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* â”€â”€ Audit Logs Tab â”€â”€ */}
          {activeTab === "Audit Logs" && (
            <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm">
              <div className="px-6 py-4 border-b border-white/10">
                <span className="text-white font-medium">Recent Admin Actions</span>
              </div>
              <div className="divide-y divide-white/5">
                {auditLogs.length === 0 && (
                  <p className="text-white/40 text-sm px-6 py-8 text-center">No audit logs yet.</p>
                )}
                {auditLogs.map((log) => (
                  <div key={log.id} className="flex items-start justify-between px-6 py-3 hover:bg-white/5 transition">
                    <div>
                      <p className="text-white text-sm">
                        <span className="font-mono text-blue-300 mr-2">{log.action}</span>
                        {log.resource && <span className="text-white/50">{log.resource}</span>}
                      </p>
                      <p className="text-white/30 text-xs mt-0.5">
                        User {log.user_id} · {log.ip_address} · {new Date(log.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  const colors = {
    blue:   "from-blue-600/20 to-blue-500/10 border-blue-500/20 text-blue-300",
    green:  "from-green-600/20 to-green-500/10 border-green-500/20 text-green-300",
    indigo: "from-indigo-600/20 to-indigo-500/10 border-indigo-500/20 text-indigo-300",
    purple: "from-purple-600/20 to-purple-500/10 border-purple-500/20 text-purple-300",
    cyan:   "from-cyan-600/20 to-cyan-500/10 border-cyan-500/20 text-cyan-300",
    orange: "from-orange-600/20 to-orange-500/10 border-orange-500/20 text-orange-300",
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-2xl p-5 backdrop-blur-sm`}>
      <span className="text-2xl">{icon}</span>
      <p className="text-white/60 text-xs font-medium uppercase tracking-wide mt-3">{label}</p>
      <h2 className="text-3xl font-bold text-white mt-1">{value ?? "—"}</h2>
    </div>
  );
}

function tabIcon(tab) {
  return { Dashboard: "📊", Documents: "📄", Users: "👥", "Audit Logs": "🔍" }[tab] || "•";
}

