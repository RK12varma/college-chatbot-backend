export default function AnalyticsCards({ stats }) {
  return (
    <div className="grid grid-cols-3 gap-6 mb-8">
      <div className="bg-zinc-900 p-6 rounded-xl">
        <p className="text-gray-400">Total Users</p>
        <h3 className="text-2xl font-bold">{stats.users}</h3>
      </div>

      <div className="bg-zinc-900 p-6 rounded-xl">
        <p className="text-gray-400">Documents</p>
        <h3 className="text-2xl font-bold">{stats.documents}</h3>
      </div>

      <div className="bg-zinc-900 p-6 rounded-xl">
        <p className="text-gray-400">Total Chunks</p>
        <h3 className="text-2xl font-bold">{stats.chunks}</h3>
      </div>
    </div>
  );
}
