import axios from "axios";

export const apiBaseURL = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export const api = axios.create({
  baseURL: apiBaseURL,
  withCredentials: true,
});

let refreshing = null;

function refreshSession() {
  if (!refreshing) {
    refreshing = axios
      .post(`${apiBaseURL}/auth/refresh`, {}, { withCredentials: true })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const status = error.response?.status;
    const cfg = error.config;
    if (status !== 401 || !cfg || cfg._authRefreshRetried) {
      return Promise.reject(error);
    }
    const path = typeof cfg.url === "string" ? cfg.url : "";
    if (
      path.includes("/auth/refresh") ||
      path.includes("/login") ||
      path.includes("/register") ||
      path.includes("/auth/oauth-bind")
    ) {
      return Promise.reject(error);
    }
    cfg._authRefreshRetried = true;
    try {
      await refreshSession();
      return api(cfg);
    } catch (e) {
      return Promise.reject(e);
    }
  }
);
