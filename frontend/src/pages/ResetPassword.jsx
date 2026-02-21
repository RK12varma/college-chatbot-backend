import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import API from "../services/api";

export default function ResetPassword() {
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const email = queryParams.get("email");

  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleReset = async () => {
    if (!email) {
      alert("Invalid request. Please start again.");
      navigate("/forgot-password");
      return;
    }

    try {
      setLoading(true);

      await API.post("/auth/reset-password", {
        email,
        new_password: newPassword,
      });

      alert("Password updated successfully");
      navigate("/login");
    } catch (err) {
      alert("Error resetting password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-300 via-blue-300 to-indigo-400 relative overflow-hidden">

      {/* Background Glow Effects */}
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl top-10 left-10"></div>
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl bottom-10 right-10"></div>

      {/* Glass Card */}
      <div className="relative backdrop-blur-xl bg-white/30 border border-white/40 shadow-2xl rounded-3xl p-10 w-96">

        <div className="flex justify-center mb-6">
          <div className="bg-white/80 shadow-md p-4 rounded-2xl text-xl">
            🔐
          </div>
        </div>

        <h2 className="text-2xl font-bold text-center text-gray-800 mb-2">
          Reset Password
        </h2>

        <p className="text-center text-gray-600 text-sm mb-6">
          Create a new secure password for your account.
        </p>

        <div className="relative mb-6">
          <input
            type={showPassword ? "text" : "password"}
            placeholder="Enter new password"
            className="w-full p-3 bg-white/70 text-gray-800 border border-white rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none pr-16 shadow-sm"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />

          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-4 top-3 text-sm font-medium text-indigo-600 hover:text-indigo-800 transition"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>

        <button
          onClick={handleReset}
          disabled={loading}
          className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 text-white py-3 rounded-xl font-semibold shadow-lg hover:scale-[1.02] transition-all duration-200 disabled:opacity-50"
        >
          {loading ? "Updating..." : "Update Password"}
        </button>

      </div>
    </div>
  );
}