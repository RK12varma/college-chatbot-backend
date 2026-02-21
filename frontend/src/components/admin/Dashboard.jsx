import { useEffect, useState } from "react";
import API from "../../services/api";
import AnalyticsCards from "./AnalyticsCards";

export default function Dashboard() {
  const [stats, setStats] = useState({
    users: 0,
    documents: 0,
    chunks: 0,
  });

  useEffect(() => {
    API.get("/admin/stats")
      .then((res) => setStats(res.data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <AnalyticsCards stats={stats} />
    </div>
  );
}
