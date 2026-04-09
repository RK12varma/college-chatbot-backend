import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ children, role }) {
  const token = localStorage.getItem("token");

  if (!token) return <Navigate to="/login" replace />;

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));

    // Check token expiry
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.clear();
      return <Navigate to="/login" replace />;
    }

    const userRole = payload.role;

    if (role) {
      const allowed = Array.isArray(role) ? role : [role];
      if (!allowed.includes(userRole)) {
        return <Navigate to="/login" replace />;
      }
    }

    return children;
  } catch {
    localStorage.clear();
    return <Navigate to="/login" replace />;
  }
}
