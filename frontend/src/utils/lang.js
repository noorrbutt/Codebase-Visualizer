export const LANG_COLOR = {
  python: "--lang-python",
  javascript: "--lang-javascript",
  typescript: "--lang-typescript",
  jsx: "--lang-javascript",
  tsx: "--lang-typescript",
  css: "--lang-css",
  html: "--lang-html",
  markdown: "--lang-markdown",
  default: "--lang-default",
};

export function getLangColor(lang, styles = getComputedStyle(document.documentElement)) {
  const variable = LANG_COLOR[lang?.toLowerCase()] || LANG_COLOR.default;
  return styles.getPropertyValue(variable).trim();
}

export const COMPLEXITY_COLOR = {
  low: "var(--accent-green)",
  medium: "var(--accent-amber)",
  high: "var(--accent-red)",
};
