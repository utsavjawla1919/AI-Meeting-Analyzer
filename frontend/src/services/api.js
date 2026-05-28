/**
 * services/api.js
 * Complete API service for AI Meeting Analyzer
 */

import axios from "axios";

// ✅ Backend URL
const BASE_URL =
  process.env.REACT_APP_API_URL ||
  "https://ai-meeting-analyzer-pc78.onrender.com/api";

// ✅ Axios instance
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ─────────────────────────────────────────────────────────────────────────────
// TOKEN HELPERS
// ─────────────────────────────────────────────────────────────────────────────

const getAccessToken = () => localStorage.getItem("access_token");

const getRefreshToken = () => localStorage.getItem("refresh_token");

const setTokens = (access, refresh) => {
  localStorage.setItem("access_token", access);

  if (refresh) {
    localStorage.setItem("refresh_token", refresh);
  }
};

export const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
};

// ─────────────────────────────────────────────────────────────────────────────
// REQUEST INTERCEPTOR
// ─────────────────────────────────────────────────────────────────────────────

api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// ─────────────────────────────────────────────────────────────────────────────
// RESPONSE INTERCEPTOR
// ─────────────────────────────────────────────────────────────────────────────

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization =
              `Bearer ${token}`;

            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = getRefreshToken();

        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        const response = await axios.post(
          `${BASE_URL}/auth/refresh`,
          {},
          {
            headers: {
              Authorization: `Bearer ${refreshToken}`,
            },
          }
        );

        const newAccessToken = response.data.access_token;

        setTokens(newAccessToken, null);

        api.defaults.headers.common.Authorization =
          `Bearer ${newAccessToken}`;

        processQueue(null, newAccessToken);

        originalRequest.headers.Authorization =
          `Bearer ${newAccessToken}`;

        return api(originalRequest);
      } catch (err) {
        processQueue(err, null);

        clearTokens();

        window.location.href = "/login";

        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// AUTH API
// ─────────────────────────────────────────────────────────────────────────────

export const authAPI = {
  register: (data) =>
    api.post("/auth/register", data),

  login: (data) =>
    api.post("/auth/login", data),

  logout: () =>
    api.post("/auth/logout"),

  getMe: () =>
    api.get("/auth/me"),

  changePassword: (data) =>
    api.put("/auth/password", data),
};

// ─────────────────────────────────────────────────────────────────────────────
// MEETINGS API
// ─────────────────────────────────────────────────────────────────────────────

export const meetingsAPI = {
  upload: (formData, onProgress) =>
    api.post("/meetings/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },

      timeout: 600000,

      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) /
              progressEvent.total
          );

          onProgress(percentCompleted);
        }
      },
    }),

  list: (params) =>
    api.get("/meetings/", { params }),

  get: (id) =>
    api.get(`/meetings/${id}`),

  status: (id) =>
    api.get(`/meetings/${id}/status`),

  update: (id, data) =>
    api.put(`/meetings/${id}`, data),

  delete: (id) =>
    api.delete(`/meetings/${id}`),

  stats: () =>
    api.get("/meetings/stats"),
};

// ─────────────────────────────────────────────────────────────────────────────
// ANALYSIS API
// ─────────────────────────────────────────────────────────────────────────────

export const analysisAPI = {
  get: (id) =>
    api.get(`/analysis/${id}`),

  transcript: (id) =>
    api.get(`/analysis/${id}/transcript`),

  sentiment: (id) =>
    api.get(`/analysis/${id}/sentiment`),

  actions: (id) =>
    api.get(`/analysis/${id}/actions`),

  keywords: (id) =>
    api.get(`/analysis/${id}/keywords`),

  retry: (id) =>
    api.post(`/analysis/${id}/retry`),

  search: (params) =>
    api.get("/analysis/search", { params }),
};

// ─────────────────────────────────────────────────────────────────────────────
// USERS API
// ─────────────────────────────────────────────────────────────────────────────

export const usersAPI = {
  getProfile: () =>
    api.get("/users/profile"),

  updateProfile: (data) =>
    api.put("/users/profile", data),

  updatePreferences: (data) =>
    api.put("/users/preferences", data),

  deleteAccount: (data) =>
    api.delete("/users/account", { data }),

  adminStats: () =>
    api.get("/users/admin/stats"),

  adminListUsers: (params) =>
    api.get("/users/admin/users", {
      params,
    }),

  adminToggleUser: (id) =>
    api.put(`/users/admin/users/${id}/toggle`),

  adminChangeRole: (id, role) =>
    api.put(`/users/admin/users/${id}/role`, {
      role,
    }),

  adminDeleteMeeting: (id) =>
    api.delete(`/users/admin/meetings/${id}`),
};

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT API
// ─────────────────────────────────────────────────────────────────────────────

export const exportAPI = {
  fullPDF: (id) =>
    api.get(`/export/${id}/pdf`, {
      responseType: "blob",
    }),

  transcriptPDF: (id) =>
    api.get(`/export/${id}/transcript`, {
      responseType: "blob",
    }),
};

// ─────────────────────────────────────────────────────────────────────────────
// DOWNLOAD HELPER
// ─────────────────────────────────────────────────────────────────────────────

export const downloadBlob = (data, filename) => {
  const url = window.URL.createObjectURL(
    new Blob([data])
  );

  const link = document.createElement("a");

  link.href = url;
  link.setAttribute("download", filename);

  document.body.appendChild(link);

  link.click();

  link.remove();
};

// ─────────────────────────────────────────────────────────────────────────────

export { setTokens };

export default api;