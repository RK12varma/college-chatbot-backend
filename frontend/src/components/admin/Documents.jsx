import { useEffect, useState } from "react";
import API from "../../services/api";

export default function Documents() {
  const [documents, setDocuments] = useState([]);

  const fetchDocuments = async () => {
    const res = await API.get("/admin/documents");
    setDocuments(res.data);
  };

  const deleteDoc = async (id) => {
    await API.delete(`/admin/documents/${id}`);
    fetchDocuments();
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Documents</h1>

      <div className="space-y-4">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="flex justify-between items-center bg-zinc-900 p-4 rounded"
          >
            <div>
              <p className="font-semibold">{doc.filename}</p>
              <p className="text-gray-400 text-sm">
                {doc.department} | Sem {doc.semester}
              </p>
            </div>

            <button
              onClick={() => deleteDoc(doc.id)}
              className="bg-red-600 px-4 py-2 rounded"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
