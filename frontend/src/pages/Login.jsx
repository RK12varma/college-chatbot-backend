import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import API from "../services/api";
import Navbar from "../components/Navbar";

export default function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) {
      alert("Please enter email and password");
      return;
    }

    setLoading(true);

    try {
      const res = await API.post("/auth/login", { email, password });

      const token = res.data.access_token;
      localStorage.setItem("token", token);

      const payload = JSON.parse(atob(token.split(".")[1]));
      const role = payload.role;

      if (role === "admin") {
        navigate("/admin");
      } else {
        navigate("/chat");
      }

    } catch (err) {
      alert(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") handleLogin();
  };

  return (
    <>
      <Navbar />

      <div className="min-h-screen pt-24 flex items-center justify-center bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400 relative overflow-hidden">

        <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl top-10 left-10"></div>
        <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl bottom-10 right-10"></div>

        <div className="relative backdrop-blur-xl bg-white/30 border border-white/40 shadow-2xl rounded-3xl p-10 w-96">

          <div className="flex justify-center mb-6">
            <div className="bg-white shadow-md p-3 rounded-xl">
              🔐
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-center text-gray-800 mb-2">
            Sign in with email
          </h2>

          <p className="text-center text-gray-600 text-sm mb-6">
            Login to Saraswati College Portal
          </p>

          <input
            type="email"
            placeholder="Email"
            className="w-full p-3 mb-4 bg-white/60 text-gray-800 border border-white rounded-xl placeholder-gray-500 focus:ring-2 focus:ring-blue-500 outline-none"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={handleKeyPress}
          />

          <div className="relative mb-4">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              className="w-full p-3 bg-white/60 text-gray-800 border border-white rounded-xl placeholder-gray-500 focus:ring-2 focus:ring-blue-500 outline-none pr-16"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handleKeyPress}
            />

            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-3 text-sm text-blue-600 hover:text-blue-800"
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>

          <div className="text-right text-sm mb-4">
            <Link to="/forgot-password" className="text-blue-700 hover:underline">
              Forgot password?
            </Link>
          </div>

          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-xl font-semibold shadow-md hover:scale-[1.02] transition disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Get Started"}
          </button>

          <p className="mt-6 text-center text-sm text-gray-700">
            Don’t have an account?{" "}
            <Link to="/register" className="text-blue-700 font-medium hover:underline">
              Create account
            </Link>
          </p>

        </div>
      </div>
    </>
  );
}