import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import API from "../services/api";

export default function VerifyResetOTP() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const email = queryParams.get("email");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    if (!otp) { alert("Enter OTP"); return; }
    setLoading(true);
    try {
      await API.post("/auth/verify-reset-otp", { email, otp });
      // pass otp forward so reset-password can include it in the request
      navigate(`/reset-password?email=${encodeURIComponent(email)}&otp=${otp}`);
    } catch (err) {
      alert(err.response?.data?.detail || "Invalid or expired OTP");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400">
      <div className="backdrop-blur-md bg-white/40 border border-white/50 shadow-2xl rounded-3xl p-10 w-96">
        <h2 className="text-2xl font-semibold text-center text-gray-800 mb-2">Check your email</h2>
        <p className="text-center text-gray-500 text-sm mb-6">
          Enter the OTP sent to <strong>{email}</strong>
        </p>
        <input
          type="text"
          placeholder="Enter OTP"
          className="w-full p-3 mb-4 bg-white text-gray-800 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-center text-xl tracking-widest"
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleVerify()}
          maxLength={6}
        />
        <button
          onClick={handleVerify}
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 rounded-xl font-semibold shadow-md hover:scale-[1.02] transition disabled:opacity-50"
        >
          {loading ? "Verifying..." : "Verify OTP"}
        </button>
      </div>
    </div>
  );
}
