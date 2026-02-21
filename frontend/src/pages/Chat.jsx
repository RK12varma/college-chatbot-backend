import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Chat() {
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const askQuestion = async () => {
    if (!question.trim()) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const res = await API.post("/chat/ask", { question });

      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: res.data.answer,
          sources: res.data.source_documents || [],
        },
      ]);

      setQuestion("");
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Server error or token missing." },
      ]);
    }

    setLoading(false);
  };

  const handleEnter = (e) => {
    if (e.key === "Enter") askQuestion();
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const handleNewChat = () => {
    setMessages([]);
  };

  return (
    <div className="min-h-screen flex bg-gradient-to-br from-sky-200 via-sky-300 to-blue-400 relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl top-10 left-10"></div>
      <div className="absolute w-96 h-96 bg-white opacity-20 rounded-full blur-3xl bottom-10 right-10"></div>

      {/* Sidebar */}
      <div
        className={`relative ${
          sidebarOpen ? "w-72" : "w-20"
        } transition-all duration-300 backdrop-blur-xl bg-white/30 border-r border-white/40 shadow-xl flex flex-col`}
      >
        {/* Toggle Button */}
        <div className="flex justify-center pt-6">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-10 h-10 rounded-full bg-white/70 backdrop-blur-md shadow-md flex items-center justify-center text-gray-700 hover:scale-110 transition-all duration-200"
          >
            {sidebarOpen ? "☰" : "☰"}
          </button>
        </div>

        {/* Menu Section */}
        <div className="flex flex-col items-center mt-10 space-y-8">
          {/* New Chat */}
          {sidebarOpen ? (
            <div className="w-full px-6">
              <button
                onClick={handleNewChat}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-2 rounded-xl shadow-md hover:scale-[1.03] transition"
              >
                + New Chat
              </button>
            </div>
          ) : (
            <button
              onClick={handleNewChat}
              className="text-2xl text-gray-700 hover:scale-110 transition"
            >
              ✎
            </button>
          )}

          {/* Example icons */}
          {!sidebarOpen && (
            <>

            </>
          )}
        </div>

        <div className="flex-1"></div>

        {/* Bottom Section */}
        <div className="flex flex-col items-center pb-6 space-y-6">
          {/* Logout */}
          {sidebarOpen ? (
            <div className="w-full px-6">
              <button
                onClick={handleLogout}
                className="w-full bg-red-500 text-white py-2 rounded-xl shadow-md hover:bg-red-600 transition"
              >
                Logout
              </button>
            </div>
          ) : (
            <button
              onClick={handleLogout}
              className="text-xl text-red-500 hover:scale-110 transition"
            >
              ⎋
            </button>
          )}

          {/* Avatar */}
          
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col p-10">
        <div className="backdrop-blur-xl bg-white/40 border border-white/40 shadow-2xl rounded-3xl flex flex-col flex-1 overflow-hidden">
          {/* Header */}
          <div className="p-8 border-b border-white/40 text-center">
            <img
              src="/college-logo.png"
              alt="College Logo"
              className="w-16 h-16 mx-auto mb-4"
            />
            <h2 className="text-2xl font-semibold text-gray-800">
              Your AI Assistant
            </h2>
            <p className="text-gray-600">
              A smarter way to work and learn.
            </p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-12 py-8 space-y-6">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-10">
                Start a conversation by asking a question.
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.role === "bot" ? (
                  <div className="bg-white/80 border border-gray-200 rounded-2xl px-6 py-4 max-w-3xl shadow-md">
                    <SmartRenderer content={msg.text} />
                  </div>
                ) : (
                  <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-2xl px-6 py-3 max-w-md shadow-md">
                    {msg.text}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="text-gray-500 animate-pulse">Thinking...</div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-white/40 bg-white/60 backdrop-blur-md px-10 py-6">
            <div className="flex items-center gap-4 bg-white border border-gray-200 rounded-2xl px-6 py-4 shadow-md">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleEnter}
                className="flex-1 bg-transparent outline-none text-gray-800 placeholder-gray-400"
                placeholder="Ask something..."
              />
              <button
                onClick={askQuestion}
                className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-2 rounded-xl hover:scale-105 transition"
              >
                ➤
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SmartRenderer({ content }) {
  return (
    <div className="prose max-w-none text-gray-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}