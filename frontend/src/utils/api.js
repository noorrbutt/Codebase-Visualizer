export async function apiFetch(path, options = {}) {
  const url = `${import.meta.env.VITE_API_URL}${path}`;
  const headers = {
    "X-API-Key": import.meta.env.VITE_API_KEY,
    ...(options.headers || {}),
  };

  return fetch(url, {
    ...options,
    headers,
  });
}
