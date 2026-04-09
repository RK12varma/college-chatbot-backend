import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import API from "../services/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const SUGGESTIONS = [
  { icon: "📊", title: "DS Results", query: "Data Science SEM-V results" },
  { icon: "👨‍🏫", title: "DS Faculty", query: "Data Science faculty members" },
  { icon: "📄", title: "DS Papers", query: "Data Science question papers SEM-V" },
  { icon: "📚", title: "DS Syllabus", query: "Data science syllabus Sem VII" },
  { icon: "💼", title: "DS Placements", query: "Data Science placement statistics" },
  { icon: "🐍", title: "Python Resources", query: "Python learning resources for Data Science" },
  { icon: "🤖", title: "ML/AI", query: "Machine Learning resources for Data Science" },
  { icon: "📈", title: "DS Career", query: "Data Science career opportunities" },
];

export default function Chat() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchSessions, setSearchSessions] = useState("");
  const [filesOpen, setFilesOpen] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const role = localStorage.getItem("role");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await API.get("/chat/sessions?page=1&page_size=50");
      setSessions(res.data.sessions ?? []);
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  };

  const loadSession = async (sessionId) => {
    try {
      const res = await API.get(`/chat/sessions/${sessionId}`);
      setCurrentSessionId(sessionId);
      setMessages(
        res.data.turns.map((t) => ({
          role: t.role === "user" ? "user" : "bot",
          text: t.content,
          sources: t.sources || [],
          pdfs: t.pdfs || [],
        }))
      );
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
    inputRef.current?.focus();
  };

  const deleteSession = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this chat?")) return;
    try {
      await API.delete(`/chat/sessions/${id}`);
      if (currentSessionId === id) handleNewChat();
      fetchSessions();
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const deleteAllSessions = async () => {
    if (!sessions.length || deletingAll) return;
    if (!window.confirm("Delete all chat history? This cannot be undone.")) return;
    setDeletingAll(true);
    try {
      await API.delete("/chat/sessions");
      handleNewChat();
      setSessions([]);
    } catch (err) {
      console.error("Failed to delete all sessions:", err);
    } finally {
      setDeletingAll(false);
    }
  };

  const askQuestion = async (qOverride) => {
    const q = (qOverride || question).trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await API.post("/chat/ask", {
        question: q,
        session_id: currentSessionId,
        use_web: webSearchEnabled,
      });

      setCurrentSessionId(res.data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: res.data.answer,
          sources: res.data.sources || [],
          pdfs: res.data.pdfs || [],
          web: res.data.web || {},
          confidence: res.data.confidence,
        },
      ]);
      fetchSessions();
    } catch (err) {
      console.error("Failed to get answer:", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: "⚠️ Something went wrong. Please try again.",
          sources: [],
          pdfs: [],
        },
      ]);
    }
    setLoading(false);
  };

  const handleLogout = () => {
    localStorage.clear();
    navigate("/login");
  };

  const filteredSessions = sessions.filter((s) =>
    (s.title || "").toLowerCase().includes(searchSessions.toLowerCase())
  );

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <div
        className={`${
          sidebarOpen ? "w-72" : "w-0 overflow-hidden"
        } transition-all duration-300 bg-gray-900 flex flex-col shrink-0`}
      >
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-600 text-gray-300 hover:bg-gray-800 transition text-sm font-medium"
          >
            <span>✏️</span>
            <span>New Chat</span>
          </button>
          <button
            onClick={deleteAllSessions}
            disabled={!sessions.length || deletingAll}
            className="mt-2 w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border border-red-700/40 text-red-300 hover:bg-red-900/20 transition text-xs font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span>🗑️</span>
            <span>{deletingAll ? "Deleting..." : "Delete All Chats"}</span>
          </button>
        </div>

        <div className="px-3 pt-3 pb-1">
          <input
            value={searchSessions}
            onChange={(e) => setSearchSessions(e.target.value)}
            placeholder="Search chats..."
            className="w-full bg-gray-800 text-gray-300 text-xs px-3 py-2 rounded-lg border border-gray-700 outline-none focus:border-gray-500 placeholder-gray-500"
          />
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {filteredSessions.length === 0 && (
            <p className="text-gray-500 text-xs text-center mt-8 px-4">No conversations yet</p>
          )}
          {filteredSessions.map((s) => (
            <div
              key={s.id}
              onClick={() => loadSession(s.id)}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition text-sm ${
                currentSessionId === s.id
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              }`}
            >
              <span className="text-xs">💬</span>
              <span className="truncate flex-1 text-xs">{s.title || "Untitled"}</span>
              <button
                onClick={(e) => deleteSession(s.id, e)}
                className="hidden group-hover:block text-gray-500 hover:text-red-400 text-xs shrink-0"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-gray-700 space-y-1">
          <button
            onClick={() => setWebSearchEnabled(!webSearchEnabled)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition ${
              webSearchEnabled
                ? "bg-blue-600/20 text-blue-400 hover:bg-blue-600/30"
                : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            }`}
          >
            <span>{webSearchEnabled ? "🌐" : "🔒"}</span>
            <span>{webSearchEnabled ? "Web Search ON" : "Web Search OFF"}</span>
          </button>
          {role === "admin" && (
            <button
              onClick={() => navigate("/admin")}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition"
            >
              <span>⚙️</span> Admin Panel
            </button>
          )}
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-red-400 hover:bg-gray-800 transition"
          >
            <span>⎋</span> Sign Out
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white shrink-0">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition"
          >
            ☰
          </button>
          <div className="flex items-center gap-2 flex-1">
            <div className="w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-white text-xs font-bold">DS</span>
            </div>
            <span className="font-semibold text-gray-800 text-sm">Data Science Assistant</span>
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">DS Department</span>
            {webSearchEnabled && (
              <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">🌐 Web Search</span>
            )}
          </div>
          <button
            onClick={() => setFilesOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 border border-blue-200 transition"
          >
            <span>📁</span> Files
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onSuggest={(s) => { setQuestion(s); inputRef.current?.focus(); }} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="border-t border-gray-200 bg-white px-4 py-4 shrink-0">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-3 bg-white border border-gray-300 rounded-2xl px-4 py-3 shadow-sm focus-within:border-blue-400 focus-within:shadow-md transition">
              <textarea
                ref={inputRef}
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    askQuestion();
                  }
                }}
                placeholder="Ask about Data Science results, faculty, question papers, placements..."
                disabled={loading}
                rows={1}
                className="flex-1 bg-transparent outline-none text-gray-800 text-sm resize-none placeholder-gray-400 leading-6 max-h-36"
              />
              <button
                onClick={() => askQuestion()}
                disabled={loading || !question.trim()}
                className="shrink-0 w-9 h-9 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 rounded-xl flex items-center justify-center transition"
              >
                <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
            <p className="text-xs text-gray-400 text-center mt-2">Press Enter to send · Shift+Enter for new line</p>
          </div>
        </div>
      </div>

      {filesOpen && <FilesModal onClose={() => setFilesOpen(false)} />}
    </div>
  );
}

function WelcomeScreen({ onSuggest }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-12">
      <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
        <span className="text-white text-3xl font-bold">DS</span>
      </div>
      <h1 className="text-2xl font-bold text-gray-800 mb-2">Data Science Assistant</h1>
      <p className="text-gray-500 text-sm mb-10 text-center max-w-sm">
        Your AI-powered guide for the Data Science department at Saraswati College of Engineering.
        Ask me anything about results, faculty, question papers, and more.
      </p>

      <div className="grid grid-cols-2 gap-3 max-w-2xl w-full">
        {SUGGESTIONS.map((item) => (
          <button
            key={item.title}
            onClick={() => onSuggest(item.query)}
            className="flex items-center gap-3 p-4 bg-white border border-gray-200 rounded-xl hover:border-blue-300 hover:shadow-md transition text-left group"
          >
            <span className="text-2xl">{item.icon}</span>
            <div>
              <p className="text-sm font-medium text-gray-700 group-hover:text-blue-700">{item.title}</p>
              <p className="text-xs text-gray-400 truncate max-w-[140px]">{item.query}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-md max-w-xl text-sm leading-relaxed shadow-sm">
          {msg.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center shrink-0 mt-1">
        <span className="text-white text-xs font-bold">DS</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
          <div className="prose prose-sm max-w-none text-gray-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
          </div>

          {msg.pdfs?.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">📎 Downloadable Files</p>
              <div className="space-y-2">
                {msg.pdfs.map((pdf, j) => (
                  <PdfCard key={j} pdf={pdf} />
                ))}
              </div>
            </div>
          )}

          {msg.sources?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-1 items-center">
              <span className="text-xs text-gray-400">📄 Sources:</span>
              {msg.sources.map((s, j) => (
                <span
                  key={j}
                  className="text-xs bg-blue-50 text-blue-600 border border-blue-100 px-2 py-0.5 rounded-full"
                >
                  {typeof s === "string" ? s : s?.label || ""}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center shrink-0">
        <span className="text-white text-xs font-bold">DS</span>
      </div>
      <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
        <div className="flex gap-1 items-center h-5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function PdfCard({ pdf }) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async (e) => {
    e.preventDefault();
    setDownloading(true);
    try {
      const fetchUrl = pdf.url?.startsWith("/document/download")
        ? pdf.url
        : `/document/proxy-pdf?url=${encodeURIComponent(pdf.url)}`;

      const res = await API.get(fetchUrl, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = pdf.filename || "document.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 3000);
    } catch (err) {
      console.error("Download failed:", err);
      if (pdf.url?.startsWith("http")) window.open(pdf.url, "_blank");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <button
      onClick={handleDownload}
      className="w-full flex items-center gap-3 bg-gray-50 hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-xl px-4 py-3 transition group text-left"
    >
      <div className="w-9 h-9 bg-red-100 rounded-lg flex items-center justify-center shrink-0">
        <span className="text-red-600 text-sm">📄</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-700 group-hover:text-blue-700 truncate">{pdf.label}</p>
        <p className="text-xs text-gray-400 truncate">
          {pdf.filename}
          {pdf.size_kb ? ` · ${pdf.size_kb} KB` : ""}
          {pdf.semester ? ` · ${pdf.semester}` : ""}
        </p>
      </div>
      <div
        className={`shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg transition ${
          downloading ? "bg-gray-200 text-gray-500" : "bg-blue-600 text-white group-hover:bg-blue-700"
        }`}
      >
        {downloading ? "⏳..." : "⬇ Download"}
      </div>
    </button>
  );
}

function FilesModal({ onClose }) {
  const [pdfs, setPdfs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 20;

  const fetchPdfs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
      if (search) params.set("search", search);
      const res = await API.get(`/document/pdfs?${params}`);
      setPdfs(res.data.pdfs ?? []);
      setTotal(res.data.total ?? 0);
    } catch (err) {
      console.error("Failed to fetch PDFs:", err);
      setPdfs([]);
    } finally {
      setLoading(false);
    }
  }, [search, page]);

  useEffect(() => {
    fetchPdfs();
  }, [fetchPdfs]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <span className="text-lg">📁</span>
            <h2 className="font-semibold text-gray-800">Data Science Documents</h2>
            {total > 0 && (
              <span className="text-xs bg-blue-50 text-blue-600 border border-blue-100 px-2 py-0.5 rounded-full">
                {total} files
              </span>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className="px-5 py-3 border-b border-gray-100">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search DS documents..."
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 outline-none focus:border-blue-400"
          />
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : pdfs.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <p className="text-3xl mb-2">📂</p>
              <p className="text-sm">No Data Science documents found</p>
            </div>
          ) : (
            pdfs.map((pdf) => <PdfCard key={pdf.id} pdf={pdf} />)
          )}
        </div>

        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between">
            <span className="text-xs text-gray-400">Page {page} of {totalPages}</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition"
              >
                ← Prev
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
