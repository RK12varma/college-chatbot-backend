import { Link } from "react-router-dom";

export default function Sidebar() {
  const token = localStorage.getItem("token");
  let role = null;

  if (token) {
    role = JSON.parse(atob(token.split(".")[1])).role;
  }

  return (
    <div className="w-64 bg-zinc-900 p-6 border-r border-gray-800">
      <h2 className="text-xl font-bold mb-8">Dashboard</h2>

      <nav className="space-y-4">
        {role === "admin" && (
          <>
            <Link to="/admin" className="block hover:text-gray-400">
              Admin Panel
            </Link>
            <Link to="/admin/users" className="block hover:text-gray-400">
              Manage Users
            </Link>
            <Link to="/admin/documents" className="block hover:text-gray-400">
              Documents
            </Link>
          </>
        )}

        {role === "student" && (
          <>
            <Link to="/chat" className="block hover:text-gray-400">
              Chat
            </Link>
          </>
        )}

        <button
          onClick={() => {
            localStorage.removeItem("token");
            window.location.href = "/login";
          }}
          className="mt-8 text-red-400"
        >
          Logout
        </button>
      </nav>
    </div>
  );
}
