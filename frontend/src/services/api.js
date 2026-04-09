import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

// ── Request interceptor — attach access token ──────────────────────────────
API.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor — auto-refresh on 401 ────────────────────────────
API.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const res = await axios.post("http://127.0.0.1:8000/auth/refresh", {
            refresh_token: refreshToken,
          });
          const newToken = res.data.access_token;
          localStorage.setItem("token", newToken);
          original.headers.Authorization = `Bearer ${newToken}`;
          return API(original);
        } catch {
          localStorage.clear();
          window.location.href = "/login";
        }
      } else {
        localStorage.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default API;
