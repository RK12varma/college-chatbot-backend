import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import API from "../services/api";

export default function VerifyOtp() {
  const [otp, setOtp] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  const handleVerify = async () => {
    if (!otp) {
      alert("Enter OTP");
      return;
    }

    try {
      await API.post("/auth/verify-otp", { email, otp });
      alert("Email verified successfully");
      navigate("/login");
    } catch (err) {
      alert("Invalid or expired OTP");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400">

      <div className="backdrop-blur-md bg-white/40 border border-white/50 shadow-2xl rounded-3xl p-10 w-96">

        <h2 className="text-2xl font-semibold text-center text-gray-800 mb-6">
          Verify OTP
        </h2>

        <input
          type="text"
          placeholder="Enter OTP"
          className="w-full p-3 mb-6 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
        />

        <button
          onClick={handleVerify}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-xl font-semibold shadow-md hover:scale-[1.02] transition"
        >
          Verify
        </button>

      </div>
    </div>
  );
}