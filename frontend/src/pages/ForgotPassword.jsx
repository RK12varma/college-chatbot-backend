import { useState } from "react";
import API from "../services/api";
import { useNavigate, Link } from "react-router-dom";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const navigate = useNavigate();

  const handleSendOTP = async () => {
    try {
      await API.post("/auth/forgot-password", { email });
      alert("OTP sent to email");
      navigate(`/verify-reset-otp?email=${email}`);
    } catch (err) {
      alert("Error sending OTP");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400">

      <div className="backdrop-blur-md bg-white/40 border border-white/50 shadow-2xl rounded-3xl p-10 w-96">

        <h2 className="text-2xl font-semibold text-center text-gray-800 mb-6">
          Forgot Password
        </h2>

        <input
          type="email"
          placeholder="Enter email"
          className="w-full p-3 mb-6 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
          onChange={(e) => setEmail(e.target.value)}
        />

        <button
          onClick={handleSendOTP}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-xl font-semibold shadow-md hover:scale-[1.02] transition"
        >
          Send OTP
        </button>

        <p className="mt-4 text-center text-sm text-gray-700">
          Back to{" "}
          <Link to="/login" className="text-blue-700 hover:underline">
            Login
          </Link>
        </p>

      </div>
    </div>
  );
}