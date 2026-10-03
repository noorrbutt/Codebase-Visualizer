// Single source of truth for the backend base URL. Falls back to localhost only in dev;
// a production build without VITE_API_URL surfaces API_CONFIG_ERROR instead of calling "undefined/...".
const configuredBaseUrl = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/+$/, "");

export const API_BASE_URL = configuredBaseUrl || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
export const API_CONFIG_ERROR = API_BASE_URL ? null : "API URL not configured";

export async function apiFetch(path, options = {}) {
  if (API_CONFIG_ERROR) throw new Error(API_CONFIG_ERROR);

  const apiKey = (import.meta.env.VITE_API_KEY ?? "").trim();
  const headers = {
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
    ...(options.headers || {}),
  };

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
}
