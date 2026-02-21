import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function Admin() {
  const navigate = useNavigate();

  const [stats, setStats] = useState({});
  const [file, setFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const token = localStorage.getItem("token");

  const config = {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };

  const fetchStats = async () => {
    const res = await axios.get("http://127.0.0.1:8000/admin/stats", config);
    setStats(res.data);
  };

  const fetchDocuments = async () => {
    const res = await axios.get("http://127.0.0.1:8000/admin/documents", config);
    setDocuments(res.data);
  };

  const fetchUsers = async () => {
    const res = await axios.get("http://127.0.0.1:8000/admin/users", config);
    setUsers(res.data);
  };

  useEffect(() => {
    fetchStats();
    fetchDocuments();
    fetchUsers();
  }, []);

  const deleteUser = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    await axios.delete(`http://127.0.0.1:8000/admin/users/${id}`, config);
    fetchUsers();
  };

  const toggleRole = async (id) => {
    await axios.put(
      `http://127.0.0.1:8000/admin/users/${id}/role`,
      {},
      config
    );
    fetchUsers();
  };

  const handleUpload = async () => {
    if (!file) {
      alert("Select a file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    try {
      await axios.post(
        "http://127.0.0.1:8000/document/upload",
        formData,
        config
      );
      alert("Uploaded successfully");
      fetchStats();
      fetchDocuments();
    } catch {
      alert("Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleScrape = async () => {
    setLoading(true);
    try {
      await axios.post("http://127.0.0.1:8000/admin/scrape", {}, config);
      alert("Scraping done");
      fetchStats();
      fetchDocuments();
    } catch {
      alert("Scraping failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400 relative overflow-hidden">

      {/* SIDEBAR (UNCHANGED) */}
      <div
        className={`${
          sidebarOpen ? "w-72" : "w-20"
        } transition-all duration-300 backdrop-blur-xl bg-white/30 border-r border-white/40 shadow-xl flex flex-col`}
      >
        <div className="flex justify-center pt-6">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-10 h-10 rounded-full bg-black/70 shadow-md flex items-center justify-center hover:scale-110 transition"
          >
            {sidebarOpen ? "‹" : "☰"}
          </button>
        </div>

        <div className="flex flex-col items-center mt-10 space-y-8">
          {sidebarOpen ? (
            <button
              onClick={() => navigate("/chat")}
              className="w-full px-6"
            >
              <div className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-2 rounded-xl text-center shadow-md hover:scale-[1.03] transition">
                + New Chat
              </div>
            </button>
          ) : (
            <button
              onClick={() => navigate("/chat")}
              className="text-2xl text-gray-700 hover:scale-110 transition"
            >
              💬
            </button>
          )}

          {sidebarOpen ? (
            <button className="w-full px-6">
              <div className="w-full bg-white/70 py-2 rounded-xl text-center shadow-md font-semibold text-gray-800">
                Admin Dashboard
              </div>
            </button>
          ) : (
            <div className="text-2xl">📊</div>
          )}
        </div>

        <div className="flex-1"></div>

        <div className="flex flex-col items-center pb-6 space-y-6">
          {sidebarOpen ? (
            <button
              onClick={handleLogout}
              className="w-full mx-6 bg-red-500 text-white py-2 rounded-xl shadow-md hover:bg-red-600 transition"
            >
              Logout
            </button>
          ) : (
            <button
              onClick={handleLogout}
              className="text-xl text-red-500"
            >
              ⎋
            </button>
          )}

          
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="flex-1 p-10 overflow-y-auto">

        <div className="backdrop-blur-xl bg-white/75 border border-white/60 shadow-2xl rounded-3xl p-10">

          <h1 className="text-3xl font-bold mb-8 text-gray-900">
            Admin Panel
          </h1>

          <div className="grid grid-cols-3 gap-6 mb-10">
            <StatCard label="Users" value={stats.users} />
            <StatCard label="Documents" value={stats.documents} />
            <StatCard label="Chunks" value={stats.chunks} />
          </div>

          {/* Upload Card */}
          <div className="bg-white p-8 rounded-2xl mb-10 shadow-lg border border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">
              Upload Document
            </h2>

            <div className="flex items-center gap-4 mb-6">
              <label className="cursor-pointer bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-2 rounded-xl shadow-md hover:scale-105 transition">
                Choose File
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files[0])}
                  className="hidden"
                />
              </label>

              <span className="text-gray-700 text-sm">
                {file ? file.name : "No file selected"}
              </span>
            </div>

            <div className="flex gap-4">
              <button
                onClick={handleUpload}
                disabled={loading}
                className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-2 rounded-xl shadow-md hover:scale-[1.03] transition disabled:opacity-50"
              >
                Upload
              </button>

              <button
                onClick={handleScrape}
                disabled={loading}
                className="bg-indigo-500 text-white px-6 py-2 rounded-xl shadow-md hover:scale-[1.03] transition disabled:opacity-50"
              >
                Run Scraper
              </button>
            </div>
          </div>

          {/* Users Card */}
          <div className="bg-white p-8 rounded-2xl shadow-lg border border-gray-200">
            <h2 className="text-xl mb-6 font-semibold text-gray-900">
              Users
            </h2>

            <div className="space-y-4">
              {users.map((u) => (
                <div
                  key={u.id}
                  className="flex justify-between items-center bg-gray-50 p-4 rounded-xl shadow-sm border border-gray-200"
                >
                  <div>
                    <p className="font-medium text-gray-900">{u.email}</p>
                    <p className="text-sm text-gray-600">
                      Role: {u.role}
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => toggleRole(u.id)}
                      className="px-4 py-1 bg-blue-600 text-white rounded-md"
                    >
                      {u.role === "admin" ? "Demote" : "Promote"}
                    </button>

                    <button
                      onClick={() => deleteUser(u.id)}
                      className="px-4 py-1 bg-red-600 text-white rounded-md"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-200 text-center">
      <p className="text-gray-600 font-medium">{label}</p>
      <h2 className="text-3xl font-bold text-gray-900 mt-2">
        {value || 0}
      </h2>
    </div>
  );
}