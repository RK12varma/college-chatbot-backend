export default function Sidebar({ activeTab, setActiveTab }) {
  const menu = [
    { id: "dashboard", label: "Dashboard" },
    { id: "documents", label: "Documents" },
    { id: "users", label: "Users" },
  ];

  return (
    <div className="w-64 bg-zinc-900 border-r border-gray-800 p-6">
      <h2 className="text-xl font-bold mb-8">Admin Panel</h2>

      {menu.map((item) => (
        <button
          key={item.id}
          onClick={() => setActiveTab(item.id)}
          className={`block w-full text-left p-3 rounded mb-3 ${
            activeTab === item.id
              ? "bg-white text-black"
              : "hover:bg-zinc-800"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
