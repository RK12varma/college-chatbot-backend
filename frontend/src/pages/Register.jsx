import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";

export default function Register() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [department, setDepartment] = useState("");
  const [role, setRole] = useState("student");
  const [adminKey, setAdminKey] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
  if (!email || !password || !department) {
    alert("Fill all required fields");
    return;
  }

  setLoading(true);

  try {
    await axios.post("http://127.0.0.1:8000/auth/register", {
      email,
      password,
      role,
      department,
      admin_key: role === "admin" ? adminKey : null,
    });

    alert("Registration successful. Please verify OTP.");

    // 👇 Go to verify page instead of login
    navigate("/verify-otp", { state: { email } });

  } catch (err) {
    alert(err.response?.data?.detail || "Registration failed");
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400 relative overflow-hidden">

      {/* Background Glow Effects */}
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl top-10 left-10"></div>
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl bottom-10 right-10"></div>

      {/* Glass Card */}
      <div className="relative backdrop-blur-xl bg-white/40 border border-white/50 shadow-2xl rounded-3xl p-10 w-96">

        {/* College Logo */}
        <div className="flex justify-center mb-4">
          <div className="bg-white/70 backdrop-blur-md p-4 rounded-2xl shadow-lg">
            <img
              src="/college-logo.png"
              alt="Saraswati College Logo"
              className="w-16 h-16 object-contain"
            />
          </div>
        </div>

        {/* Title */}
        <h2 className="text-2xl font-semibold text-center text-gray-800 mb-6">
          Register
        </h2>

        {/* Email */}
        <input
          type="email"
          placeholder="Email"
          className="w-full p-3 mb-4 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        {/* Password */}
        <div className="relative mb-4">
          <input
            type={showPassword ? "text" : "password"}
            placeholder="Password"
            className="w-full p-3 bg-white text-gray-800 border border-gray-300 rounded-xl pr-16 focus:ring-2 focus:ring-indigo-400 outline-none"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-4 top-3 text-sm font-medium text-indigo-600 hover:text-indigo-800 transition"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>

        {/* Department */}
        <input
          type="text"
          placeholder="Department"
          className="w-full p-3 mb-4 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none"
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
        />

        {/* Role */}
        <select
          className="w-full p-3 mb-4 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <option value="student">Student</option>
          <option value="admin">Admin</option>
        </select>

        {/* Admin Secret Key (Conditional) */}
        {role === "admin" && (
          <input
            type="password"
            placeholder="Admin Secret Key"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            className="w-full p-3 mb-4 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none"
          />
        )}

        {/* Submit Button */}
        <button
          onClick={handleRegister}
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-xl font-semibold shadow-md hover:scale-[1.02] transition-all duration-200 disabled:opacity-50"
        >
          {loading ? "Creating..." : "Sign Up"}
        </button>

        {/* Login Link */}
        <p className="mt-4 text-center text-sm text-gray-700">
          Already have an account?{" "}
          <Link
            to="/login"
            className="text-blue-700 font-medium hover:underline"
          >
            Login
          </Link>
        </p>

      </div>
    </div>
  );
}