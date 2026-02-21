import axios from "axios";

/*
|--------------------------------------------------------------------------
| Axios Instance
|--------------------------------------------------------------------------
| Centralized API configuration
| All requests automatically use this baseURL
*/

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
});


/*
|--------------------------------------------------------------------------
| Request Interceptor
|--------------------------------------------------------------------------
| Automatically attaches JWT token if available
*/

API.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);


/*
|--------------------------------------------------------------------------
| AUTH APIs
|--------------------------------------------------------------------------
*/

export const registerUser = (data) => {
  return API.post("/auth/register", data);
};

export const loginUser = (data) => {
  return API.post("/auth/login", data);
};


/*
|--------------------------------------------------------------------------
| CHAT API
|--------------------------------------------------------------------------
*/

export const askQuestion = (question) => {
  return API.post("/chat/ask", { question });
};


/*
|--------------------------------------------------------------------------
| ADMIN APIs (Optional but Recommended)
|--------------------------------------------------------------------------
*/

export const getAdminSources = () => {
  return API.get("/admin/sources");
};

export const addAdminSource = (data) => {
  return API.post("/admin/sources", data);
};

export const deleteAdminSource = (id) => {
  return API.delete(`/admin/sources/${id}`);
};


/*
|--------------------------------------------------------------------------
| Export Default
|--------------------------------------------------------------------------
*/

export default API;
