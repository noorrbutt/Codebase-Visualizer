export function normalizeRepoInput(input) {
  const value = input.trim();
  if (!value) {
    return { error: "Paste a GitHub repository URL or owner/repo to get started." };
  }

  const hasGitHubHost = /^https?:\/\/(?:www\.)?github\.com(?:\/|$)/i.test(value)
    || /^(?:www\.)?github\.com(?:\/|$)/i.test(value);
  const candidate = /^[a-z][a-z\d+.-]*:\/\//i.test(value)
    ? value
    : hasGitHubHost
      ? `https://${value}`
      : `https://github.com/${value}`;

  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return { error: "Enter a valid GitHub repository URL or owner/repo." };
  }

  if (
    !["http:", "https:"].includes(parsed.protocol)
    || !["github.com", "www.github.com"].includes(parsed.hostname.toLowerCase())
    || parsed.port
    || parsed.username
    || parsed.password
  ) {
    return { error: "Repository must be hosted on github.com." };
  }

  let segments;
  try {
    segments = parsed.pathname.split("/").filter(Boolean).slice(0, 2).map(decodeURIComponent);
  } catch {
    return { error: "Enter a valid GitHub repository URL or owner/repo." };
  }

  if (segments.length < 2 || !segments[0] || !segments[1]) {
    return { error: "Enter a GitHub repository as owner/repo." };
  }

  const [owner, rawRepo] = segments;
  const repo = rawRepo.replace(/\.git$/i, "");
  if (
    !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(owner)
    || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(repo)
  ) {
    return { error: "Enter a valid GitHub repository as owner/repo." };
  }

  return { url: `https://github.com/${owner}/${repo}` };
}

export function errorMessage(body) {
  if (typeof body?.detail === "string") return body.detail;

  if (Array.isArray(body?.detail)) {
    const messages = body.detail
      .map((item) => item?.msg)
      .filter((message) => typeof message === "string" && message.length > 0);
    if (messages.length) return messages.join("; ");
  }

  if (typeof body?.message === "string" && body.message.length > 0) {
    return body.message;
  }

  return "Analysis failed";
}
