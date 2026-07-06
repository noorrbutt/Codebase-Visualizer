export const LANG_COLOR = {
  python: "#3B82F6",
  javascript: "#F59E0B",
  typescript: "#6366F1",
  jsx: "#F59E0B",
  tsx: "#6366F1",
  css: "#8B5CF6",
  html: "#EF4444",
  markdown: "#6B7280",
  default: "#9CA3AF",
};

export function getLangColor(lang) {
  return LANG_COLOR[lang?.toLowerCase()] || LANG_COLOR.default;
}

export const COMPLEXITY_COLOR = {
  low: "#10B981",
  medium: "#F59E0B",
  high: "#EF4444",
};

export const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";