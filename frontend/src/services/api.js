/**
 * services/api.js — Axios instance + all API call functions.
 * JWT token is injected into every request via an interceptor.
 * 401 responses auto-refresh the access token once, then redirect to login.
 */

import axios from "axios";

const BASE_URL = process.env.REACT_APP_API_URL || "/api";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,   // 2 min (long for file uploads)
  headers: { "Content-Type": "application/json" },
});

// ── Token helpers ──────────────────────────────────────────────────────────────
const getAccessToken  = () => localStorage.getItem("access_token");
const getRefreshToken = () => localStorage.getItem("refresh_token");
const setTokens = (access, refresh) => {
  localStorage.setItem("access_token",  access);
  if (refresh) localStorage.setItem("refresh_token", refresh);
};
export const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
};

// ── Request interceptor — attach Bearer token ──────────────────────────────────
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor — silent token refresh ────────────────────────────────
let _refreshing = false;
let _queue = [];

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      if (_refreshing) {
        return new Promise((resolve, reject) =>
          _queue.push({ resolve, reject })
        ).then(() => api(original));
      }

      original._retry = true;
      _refreshing     = true;

      try {
        const refresh = getRefreshToken();
        if (!refresh) throw new Error("No refresh token");

        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, null, {
          headers: { Authorization: `Bearer ${refresh}` },
        });

        setTokens(data.access_token, null);
        _queue.forEach(({ resolve }) => resolve());
        _queue = [];
        return api(original);
      } catch (err) {
        _queue.forEach(({ reject }) => reject(err));
        _queue = [];
        clearTokens();
        window.location.href = "/login";
        return Promise.reject(err);
      } finally {
        _refreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

// ══════════════════════════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════════════════════════
export const authAPI = {
  register: (data)   => api.post("/auth/register", data),
  login:    (data)   => api.post("/auth/login",    data),
  logout:   ()       => api.post("/auth/logout"),
  getMe:    ()       => api.get("/auth/me"),
  changePassword: (data) => api.put("/auth/password", data),
};

// ══════════════════════════════════════════════════════════════════════════════
// MEETINGS
// ══════════════════════════════════════════════════════════════════════════════
export const meetingsAPI = {
  upload: (formData, onProgress) =>
    api.post("/meetings/upload", formData, {
      headers:         { "Content-Type": "multipart/form-data" },
      timeout:         600_000,
      onUploadProgress: (e) =>
        onProgress?.(Math.round((e.loaded / e.total) * 100)),
    }),

  list:   (params)     => api.get("/meetings/",          { params }),
  get:    (id)         => api.get(`/meetings/${id}`),
  status: (id)         => api.get(`/meetings/${id}/status`),
  update: (id, data)   => api.put(`/meetings/${id}`, data),
  delete: (id)         => api.delete(`/meetings/${id}`),
  stats:  ()           => api.get("/meetings/stats"),
};

// ══════════════════════════════════════════════════════════════════════════════
// ANALYSIS
// ══════════════════════════════════════════════════════════════════════════════
export const analysisAPI = {
  get:        (id)    => api.get(`/analysis/${id}`),
  transcript: (id)    => api.get(`/analysis/${id}/transcript`),
  sentiment:  (id)    => api.get(`/analysis/${id}/sentiment`),
  actions:    (id)    => api.get(`/analysis/${id}/actions`),
  keywords:   (id)    => api.get(`/analysis/${id}/keywords`),
  retry:      (id)    => api.post(`/analysis/${id}/retry`),
  search:     (params)=> api.get("/analysis/search", { params }),
};

// ══════════════════════════════════════════════════════════════════════════════
// USERS
// ══════════════════════════════════════════════════════════════════════════════
export const usersAPI = {
  getProfile:        ()     => api.get("/users/profile"),
  updateProfile:     (data) => api.put("/users/profile",     data),
  updatePreferences: (data) => api.put("/users/preferences", data),
  deleteAccount:     (data) => api.delete("/users/account",  { data }),

  // Admin
  adminStats:        ()     => api.get("/users/admin/stats"),
  adminListUsers:    (p)    => api.get("/users/admin/users",        { params: p }),
  adminToggleUser:   (id)   => api.put(`/users/admin/users/${id}/toggle`),
  adminChangeRole:   (id,r) => api.put(`/users/admin/users/${id}/role`, { role: r }),
  adminDeleteMeeting:(id)   => api.delete(`/users/admin/meetings/${id}`),
};

// ══════════════════════════════════════════════════════════════════════════════
// EXPORT
// ══════════════════════════════════════════════════════════════════════════════
export const exportAPI = {
  fullPDF:       (id) => api.get(`/export/${id}/pdf`,        { responseType: "blob" }),
  transcriptPDF: (id) => api.get(`/export/${id}/transcript`, { responseType: "blob" }),
};

// ── Blob download helper ────────────────────────────────────────────────────────
export function downloadBlob(data, filename) {
  const url  = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
  const link = document.createElement("a");
  link.href  = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export { setTokens };
export default api;
