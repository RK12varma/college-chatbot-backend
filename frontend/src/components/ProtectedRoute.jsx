import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ children, role }) {
  const token = localStorage.getItem("token");

  // No token → redirect
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const userRole = payload.role;

    // If role is provided
    if (role) {
      // Support multiple roles (array)
      if (Array.isArray(role)) {
        if (!role.includes(userRole)) {
          return <Navigate to="/login" replace />;
        }
      } else {
        // Single role
        if (userRole !== role) {
          return <Navigate to="/login" replace />;
        }
      }
    }

    return children;

  } catch (error) {
    // Invalid token → clear + redirect
    localStorage.removeItem("token");
    return <Navigate to="/login" replace />;
  }
}