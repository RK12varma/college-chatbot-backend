import { useEffect, useState } from "react";
import API from "../../services/api";

export default function Users() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    API.get("/admin/users")
      .then((res) => setUsers(res.data))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Users</h1>

      <div className="space-y-4">
        {users.map((user) => (
          <div
            key={user.id}
            className="bg-zinc-900 p-4 rounded flex justify-between"
          >
            <div>
              <p>{user.email}</p>
              <p className="text-gray-400 text-sm">{user.role}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
