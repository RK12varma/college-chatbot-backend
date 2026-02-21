import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <div className="fixed top-0 left-0 w-full z-50 backdrop-blur-xl bg-white/30 border-b border-white/40 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-8 py-4">

        {/* Logo + College Name */}
        <div className="flex items-center gap-4">
          <img
            src="/college-logo.png"
            alt="College Logo"
            className="w-10 h-10 object-contain"
          />
          <h1 className="text-lg md:text-xl font-semibold text-gray-800 tracking-wide">
            Saraswati College of Engineering
          </h1>
        </div>

      </div>
    </div>
  );
}