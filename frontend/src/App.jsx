import { useState, useEffect, useRef } from "react";
import DashboardPage from "./DashboardPage";
import { getLangColor } from "./utils/lang";
import { apiFetch } from "./utils/api";
import { pollRepoStatus } from "./utils/poll";

function getRepoPath(owner, repo) {
  return `/r/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
}

function parseRepoPath(pathname) {
  const match = pathname.match(/^\/r\/([^/]+)\/([^/]+)\/?$/);
  if (!match) return null;

  try {
    return { owner: decodeURIComponent(match[1]), repo: decodeURIComponent(match[2]) };
  } catch {
    return null;
  }
}

function HomePage({ onAnalyze, onOpenRepo, loading, externalError, onClearError, initialUrl }) {
  const [url, setUrl] = useState(initialUrl);
  const [error, setError] = useState("");
  const [recentRepos, setRecentRepos] = useState([]);

  useEffect(() => {
    let active = true;
    apiFetch("/repos/?status=ready&limit=6")
      .then((response) => {
        if (!response.ok) throw new Error("Could not load recently analyzed repositories");
        return response.json();
      })
      .then((repos) => {
        if (active && Array.isArray(repos)) setRecentRepos(repos);
      })
      .catch(() => {
        if (active) setRecentRepos([]);
      });

    return () => {
      active = false;
    };
  }, []);

  const examples = [
    { owner: "pallets", repo: "flask" },
    { owner: "tiangolo", repo: "fastapi" },
    { owner: "expressjs", repo: "express" },
    { owner: "vitejs", repo: "vite" },
  ];

  const handleExampleClick = (example) => {
    const exampleUrl = `https://github.com/${example.owner}/${example.repo}`;
    const readyRepo = recentRepos.find(
      (repo) => repo.github_url.replace(/\/+$/, "").toLowerCase() === exampleUrl.toLowerCase(),
    );
    if (readyRepo) {
      onOpenRepo(readyRepo);
    } else {
      setError("");
      onClearError();
      onAnalyze(exampleUrl);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    onClearError();
    if (!url.trim()) return setError("Paste a GitHub URL to get started.");
    if (!url.includes("github.com/")) return setError("Must be a github.com URL.");
    onAnalyze(url.trim());
  };

  const errorMessage = error || externalError;

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "var(--bg)", backgroundImage: "radial-gradient(var(--grid-dot) 1px, transparent 1px)", backgroundSize: "24px 24px" }}>
      <div style={{ maxWidth: 560, width: "100%", textAlign: "center" }}>
        <div style={{ marginBottom: "2.5rem" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: "1.5rem" }}>
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <circle cx="5" cy="5" r="3" fill="var(--fg)" />
              <circle cx="17" cy="5" r="3" fill="var(--fg)" />
              <circle cx="11" cy="17" r="3" fill="var(--fg)" />
              <line x1="5" y1="5" x2="17" y2="5" stroke="var(--fg)" strokeWidth="1.5" />
              <line x1="5" y1="5" x2="11" y2="17" stroke="var(--fg)" strokeWidth="1.5" />
              <line x1="17" y1="5" x2="11" y2="17" stroke="var(--fg)" strokeWidth="1.5" />
            </svg>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, fontWeight: 500, letterSpacing: "0.06em", color: "var(--fg)" }}>CODEBASE VISUALIZER</span>
          </div>
          <h1 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "clamp(2rem, 5vw, 3rem)", fontWeight: 400, lineHeight: 1.15, color: "var(--fg)", margin: "0 0 1rem" }}>
            See how your code<br />connects.
          </h1>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 16, color: "var(--muted)", lineHeight: 1.6, margin: 0 }}>
            Paste any public GitHub repository and get an interactive dashboard in seconds.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", gap: 0, border: "1.5px solid var(--border)", borderRadius: 10, overflow: "hidden", background: "var(--surface)", transition: "border-color 0.15s", boxShadow: "var(--shadow-md)" }}>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              aria-label="GitHub repository URL"
              disabled={loading}
              style={{ flex: 1, border: "none", outline: "none", padding: "14px 16px", fontFamily: "'DM Mono', monospace", fontSize: 13, color: "var(--fg)", background: "transparent", minWidth: 0 }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{ padding: "14px 24px", background: "var(--fg)", color: "var(--surface)", border: "none", cursor: loading ? "not-allowed" : "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 500, whiteSpace: "nowrap", opacity: loading ? 0.6 : 1 }}
            >
              {loading ? "Analyzing…" : "Visualize →"}
            </button>
          </div>
          {errorMessage && <p role="alert" style={{ margin: "8px 0 0", fontSize: 13, color: "var(--status-error)", fontFamily: "'DM Sans', sans-serif" }}>{errorMessage}</p>}
        </form>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 24, flexWrap: "wrap" }}>
          {['Python', 'JavaScript', 'TypeScript', 'HTML/CSS'].map((l) => (
            <span key={l} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: getLangColor(l.toLowerCase().split("/")[0]), display: "inline-block" }} />
              {l}
            </span>
          ))}
        </div>

        <section aria-label="Example repositories" style={{ marginTop: "2rem" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
            Try an example
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: 8, flexWrap: "wrap" }}>
            {examples.map((example) => (
              <button
                key={`${example.owner}/${example.repo}`}
                type="button"
                disabled={loading}
                onClick={() => handleExampleClick(example)}
                style={{ padding: "8px 12px", border: "1px solid var(--border)", borderRadius: 999, background: "var(--surface)", color: "var(--fg)", cursor: loading ? "not-allowed" : "pointer", fontFamily: "'DM Mono', monospace", fontSize: 12, opacity: loading ? 0.6 : 1 }}
              >
                {example.owner}/{example.repo}
              </button>
            ))}
          </div>
        </section>

        {recentRepos.length > 0 && (
          <section aria-label="Recently analyzed repositories" style={{ marginTop: "1.5rem" }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
              Recently analyzed
            </p>
            <div style={{ display: "flex", justifyContent: "center", gap: 8, flexWrap: "wrap" }}>
              {recentRepos.map((repo) => (
                <button
                  key={repo.id}
                  type="button"
                  disabled={loading}
                  onClick={() => onOpenRepo(repo)}
                  style={{ padding: "8px 12px", border: "1px solid var(--border)", borderRadius: 999, background: "var(--surface)", color: "var(--fg)", cursor: loading ? "not-allowed" : "pointer", fontFamily: "'DM Mono', monospace", fontSize: 12, opacity: loading ? 0.6 : 1 }}
                >
                  {repo.owner}/{repo.repo_name}
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}


function LoadingPage({ repoName, stage }) {
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d + 1) % 4), 400);
    return () => clearInterval(t);
  }, []);

  const stages = ["fetching", "parsing", "summarizing"];
  const currentStageIndex = stages.indexOf(stage);
  const steps = [
    { label: "Fetching repository tree and source files", stage: "fetching" },
    { label: "Parsing dependencies", stage: "parsing" },
    { label: "Generating AI summary", stage: "summarizing" },
  ].map((step, index) => ({
    ...step,
    done: index < currentStageIndex,
    active: index === currentStageIndex,
  }));

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "var(--bg)" }}>
      <div style={{ maxWidth: 400, width: "100%", textAlign: "center" }}>
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ width: 48, height: 48, margin: "0 auto 1.5rem", position: "relative" }}>
            <svg width="48" height="48" viewBox="0 0 48 48" style={{ animation: "spin 2s linear infinite" }}>
              <circle cx="24" cy="24" r="20" fill="none" stroke="var(--border)" strokeWidth="3" />
              <circle cx="24" cy="24" r="20" fill="none" stroke="var(--fg)" strokeWidth="3" strokeDasharray="30 96" strokeLinecap="round" />
            </svg>
          </div>
          <p role="status" aria-live="polite" style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "var(--muted)", letterSpacing: "0.08em", margin: "0 0 0.5rem" }}>Analyzing {repoName || "repository"}</p>
          <h2 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: 22, fontWeight: 400, color: "var(--fg)", margin: "0 0 2rem" }}>
            {repoName || "repository"}{"...".slice(0, dots + 1)}
          </h2>
        </div>
        <div style={{ textAlign: "left" }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: i < steps.length - 1 ? "1px solid var(--border)" : "none" }}>
              <div style={{ width: 20, height: 20, borderRadius: "50%", background: s.done || s.active ? "var(--fg)" : "var(--surface-soft)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.3s" }}>
                {s.done
                  ? <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 5l2.5 2.5L8 3" stroke="var(--surface)" strokeWidth="1.5" fill="none" strokeLinecap="round" /></svg>
                  : <div style={{ width: 6, height: 6, borderRadius: "50%", background: s.active ? "var(--surface)" : "var(--subtlest)" }} />
                }
              </div>
              <span role={s.active ? "status" : undefined} aria-live={s.active ? "polite" : undefined} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: s.done || s.active ? "var(--fg)" : "var(--muted)", transition: "color 0.3s" }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState(() => parseRepoPath(window.location.pathname) ? "loading" : "home");
  const [loading, setLoading] = useState(() => Boolean(parseRepoPath(window.location.pathname)));
  const [repoName, setRepoName] = useState(() => {
    const repoPath = parseRepoPath(window.location.pathname);
    return repoPath ? `${repoPath.owner}/${repoPath.repo}` : "";
  });
  const [pollStage, setPollStage] = useState("fetching");
  const [data, setData] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [failureMessage, setFailureMessage] = useState("");
  const [retryUrl, setRetryUrl] = useState("");
  const [pathname, setPathname] = useState(() => window.location.pathname);
  const pollRef = useRef(null);
  const routeGenerationRef = useRef(0);
  const routeActionsRef = useRef(null);

  const analyze = async (url, isCurrent = () => true) => {
    setLoading(true);
    setView("loading");
    setRetryUrl(url);
    setFailureMessage("");
    const parts = url.replace("https://github.com/", "").split("/");
    setRepoName(parts.slice(0, 2).join("/"));
    try {
      const res = await apiFetch(`/repos/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ github_url: url }),
      });
      if (!isCurrent()) return;
      if (!res.ok) {
        const errorBody = await res.json().catch(() => null);
        const detail = errorBody?.detail || errorBody?.message || res.statusText || "Analysis failed";
        throw new Error(detail);
      }
      const json = await res.json();
      if (!isCurrent()) return;
      if (json.status === "ready") {
        fetchRepo(json.id, true, isCurrent);
        return;
      }
      setData(json);
      setPollStage("fetching");
      startPolling(json.id, isCurrent);
    } catch (error) {
      if (!isCurrent()) return;
      const message = error instanceof Error ? error.message : "Analysis failed";
      setLoading(false);
      setView("home");
      setAnalysisError(error instanceof TypeError ? `Could not connect to the backend. ${message}` : message);
    }
  };

  const fetchRepo = async (id, pushHistory = true, isCurrent = () => true) => {
    try {
      const res = await apiFetch(`/repos/${id}`);
      if (!res.ok) throw new Error("Could not load repository");
      const json = await res.json();
      if (!isCurrent()) return;
      setData(json);
      setLoading(false);
      setView("dashboard");
      if (pushHistory) {
        const path = getRepoPath(json.owner, json.repo_name);
        if (window.location.pathname !== path) window.history.pushState(null, "", path);
      }
    } catch {
      if (!isCurrent()) return;
      setLoading(false);
      setView("home");
      setAnalysisError("Failed to load repository after analysis completed.");
    }
  };

  const openReadyRepo = (repo) => {
    setLoading(true);
    setView("loading");
    setRepoName(`${repo.owner}/${repo.repo_name}`);
    setAnalysisError("");
    fetchRepo(repo.id);
  };

  const startPolling = (id, isCurrent = () => true) => {
    pollRef.current?.();
    pollRef.current = pollRepoStatus(id, {
      onStatus: (_status, stage) => {
        if (isCurrent()) setPollStage(stage);
      },
      onReady: () => fetchRepo(id, true, isCurrent),
      onError: (message) => {
        if (!isCurrent()) return;
        pollRef.current = null;
        setFailureMessage(message);
        setLoading(false);
        setView("error");
      },
    });
  };

  useEffect(() => {
    routeActionsRef.current = { analyze, startPolling };
  });

  useEffect(() => {
    const handlePopState = () => {
      const currentPath = window.location.pathname;
      const repoPath = parseRepoPath(currentPath);
      routeGenerationRef.current += 1;
      pollRef.current?.();
      pollRef.current = null;
      setPathname(currentPath);

      if (repoPath) {
        setLoading(true);
        setView("loading");
        setRepoName(`${repoPath.owner}/${repoPath.repo}`);
        setAnalysisError("");
        setFailureMessage("");
      } else {
        setView("home");
        setData(null);
        setLoading(false);
        setRepoName("");
        setFailureMessage("");
        setAnalysisError("");
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const generation = routeGenerationRef.current + 1;
    routeGenerationRef.current = generation;
    pollRef.current?.();
    pollRef.current = null;
    const isCurrent = () => routeGenerationRef.current === generation;
    const repoPath = parseRepoPath(pathname);

    if (!repoPath) return;

    const { owner, repo } = repoPath;

    apiFetch(`/repos/by-name/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`)
      .then(async (response) => {
        if (!isCurrent()) return;
        if (response.status === 404) {
          await routeActionsRef.current.analyze(`https://github.com/${owner}/${repo}`, isCurrent);
          return;
        }
        if (!response.ok) throw new Error("Could not load repository");

        const json = await response.json();
        if (!isCurrent()) return;
        if (json.status === "ready") {
          setData(json);
          setLoading(false);
          setView("dashboard");
        } else if (json.status === "parsing") {
          setPollStage("fetching");
          routeActionsRef.current.startPolling(json.id, isCurrent);
        } else {
          setFailureMessage("This repository analysis failed. Try analyzing it again.");
          setLoading(false);
          setView("error");
        }
      })
      .catch((error) => {
        if (!isCurrent()) return;
        setLoading(false);
        setView("home");
        setAnalysisError(error instanceof Error ? error.message : "Could not load repository");
      });

    return () => {
      if (routeGenerationRef.current === generation) {
        routeGenerationRef.current += 1;
        pollRef.current?.();
        pollRef.current = null;
      }
    };
  }, [pathname]);

  const reset = () => {
    pollRef.current?.();
    pollRef.current = null;
    window.history.pushState(null, "", "/");
    setPathname("/");
    setView("home");
    setData(null);
    setLoading(false);
    setRepoName("");
    setPollStage("fetching");
    setFailureMessage("");
    setRetryUrl("");
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@400;500&family=DM+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
          color-scheme: light;
          --bg: #F8F9FA;
          --surface: #FFFFFF;
          --surface-raised: #FFFFFF;
          --surface-soft: #F3F4F6;
          --export-background: #FFFFFF;
          --border: #E5E7EB;
          --border-soft: #F3F4F6;
          --fg: #111827;
          --fg-dim: #374151;
          --muted: #6B7280;
          --subtle: #9CA3AF;
          --subtlest: #D1D5DB;
          --grid-dot: #E5E7EB;
          --input-bg: #FAFAF9;
          --source-bg: #FAFAF9;
          --source-fg: #1F2937;
          --selected-bg: #F9FAFB;
          --selected-hover: #FAFAF9;
          --connected-bg: #F3F4F6;
          --canvas-edge: rgba(0,0,0,0.06);
          --canvas-edge-muted: rgba(0,0,0,0.015);
          --canvas-edge-highlight: rgba(99,102,241,0.55);
          --shadow-sm: 0 1px 2px rgba(16,24,40,0.04);
          --shadow-md: 0 1px 6px rgba(0,0,0,0.06);
          --shadow-lg: 0 2px 8px rgba(0,0,0,0.07);
          --accent-blue: #3B82F6;
          --accent-green: #10B981;
          --accent-purple: #8B5CF6;
          --accent-amber: #F59E0B;
          --accent-red: #EF4444;
          --accent-indigo: #6366F1;
          --accent-pink: #EC4899;
          --success-bg: #F0FDF4;
          --success-fg: #166534;
          --warning-bg: #FFFBEB;
          --warning-badge: #FEF9C3;
          --warning-border: #FDE68A;
          --warning-fg: #92400E;
          --danger-bg: #FEF2F2;
          --danger-fg: #DC2626;
          --card-blue-bg: #EEF2FF;
          --card-blue-fg: #4F46E5;
          --card-green-bg: #ECFDF5;
          --card-green-fg: #059669;
          --card-red-bg: #FEF2F2;
          --card-red-fg: #DC2626;
          --card-purple-bg: #F5F3FF;
          --card-purple-fg: #7C3AED;
          --card-orange-bg: #FFF7ED;
          --card-orange-fg: #EA580C;
          --card-gray-bg: #F3F4F6;
          --card-gray-fg: #4B5563;
          --chart-grid: #F0F1F3;
          --chart-label: #B3B7BE;
          --chart-unknown: #E5E7EB;
          --role-test: #9CA3AF;
          --role-static: #D1D5DB;
          --status-error: #EF4444;
          --status-link: #2563EB;
          --lang-python: #3B82F6;
          --lang-javascript: #F59E0B;
          --lang-typescript: #6366F1;
          --lang-css: #8B5CF6;
          --lang-html: #EF4444;
          --lang-markdown: #6B7280;
          --lang-default: #9CA3AF;
          --role-entry: #6366F1;
          --role-api: #3B82F6;
          --role-model: #10B981;
          --role-service: #F59E0B;
          --role-utility: #8B5CF6;
          --role-config: #EC4899;
          --complexity-unknown: #E5E7EB;
        }
        @media (prefers-color-scheme: dark) {
          :root {
            color-scheme: dark;
            --bg: #111318;
            --surface: #1B1E26;
            --surface-raised: #242832;
            --surface-soft: #292E39;
            --border: #353B49;
            --border-soft: #2A303B;
            --fg: #F3F4F6;
            --fg-dim: #D1D5DB;
            --muted: #A1A8B5;
            --subtle: #8B93A1;
            --subtlest: #626B79;
            --grid-dot: #303642;
            --input-bg: #242832;
            --source-bg: #171A21;
            --source-fg: #D1D5DB;
            --selected-bg: #292E39;
            --selected-hover: #303642;
            --connected-bg: #303642;
            --canvas-edge: rgba(203,213,225,0.22);
            --canvas-edge-muted: rgba(203,213,225,0.035);
            --canvas-edge-highlight: rgba(129,140,248,0.75);
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.25);
            --shadow-md: 0 1px 6px rgba(0,0,0,0.3);
            --shadow-lg: 0 2px 8px rgba(0,0,0,0.4);
            --success-bg: #163225;
            --success-fg: #86EFAC;
            --warning-bg: #332B19;
            --warning-badge: #443819;
            --warning-border: #655226;
            --warning-fg: #FCD34D;
            --danger-bg: #3A2024;
            --danger-fg: #FCA5A5;
            --card-blue-bg: #252D4B;
            --card-blue-fg: #A5B4FC;
            --card-green-bg: #18362D;
            --card-green-fg: #6EE7B7;
            --card-red-bg: #3A2024;
            --card-red-fg: #FCA5A5;
            --card-purple-bg: #302748;
            --card-purple-fg: #C4B5FD;
            --card-orange-bg: #3A2D1D;
            --card-orange-fg: #FDBA74;
            --card-gray-bg: #303642;
            --card-gray-fg: #CBD5E1;
            --chart-grid: #343A46;
            --chart-label: #7D8695;
            --chart-unknown: #424957;
            --role-test: #9CA3AF;
            --role-static: #6B7280;
            --status-error: #FCA5A5;
            --status-link: #93C5FD;
            --role-test: #9CA3AF;
            --role-static: #6B7280;
            --complexity-unknown: #424957;
          }
        }
        body { background: var(--bg); color: var(--fg); }
        button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, [role="tabpanel"]:focus-visible { outline: 2px solid var(--status-link); outline-offset: 2px; }
        input:focus { border-color: var(--fg) !important; }
        ::-webkit-scrollbar-thumb { background: var(--border); }
        .dashboard-root { min-width: 0; }
        .dashboard-header { gap: 8px; }
        .dashboard-header-brand { min-width: 0; }
        .dashboard-tabs { flex-shrink: 0; }
        .dashboard-overview { min-width: 0; }
        .dashboard-chart-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        .dashboard-bottom-grid { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
        .dashboard-graph-layout { min-width: 0; }
        .dashboard-detail-panel { min-width: 0; }
        .graph-export-actions { right: 12px !important; }
        .graph-export-toast { right: 12px !important; }
        @media (max-width: 800px) {
          .dashboard-header { height: auto !important; min-height: 52px; flex-wrap: wrap; padding: 8px 12px !important; }
          .dashboard-header-brand { flex: 1 1 60%; }
          .dashboard-tabs { order: 3; width: 100%; justify-content: center; }
          .dashboard-graph-layout, .dashboard-files-layout { flex-direction: column !important; }
          .dashboard-graph-canvas { flex: 1 1 55% !important; min-height: 200px; }
          .dashboard-graph-layout .dashboard-detail-panel { flex: 0 0 40%; width: 100% !important; height: auto; border-left: 0 !important; border-top: 1px solid var(--border); }
          .dashboard-file-list { flex: 1 1 50%; min-height: 0; height: auto !important; }
          .dashboard-files-layout .dashboard-detail-panel { flex: 1 1 50%; width: 100% !important; height: auto; border-left: 0 !important; border-top: 1px solid var(--border); }
          .dashboard-graph-layout .graph-export-actions { top: 60px !important; }
          .dashboard-graph-layout .graph-export-toast { top: 100px !important; }
          .dashboard-graph-layout .graph-export-actions.has-selection { top: 150px !important; }
          .dashboard-graph-layout .graph-export-toast.has-selection { top: 190px !important; }
          .graph-selected-node { top: 102px !important; max-width: calc(100% - 24px); }
        }
        @media (max-width: 480px) {
          .dashboard-overview { padding: 12px !important; }
          .dashboard-header-brand > span:nth-of-type(1) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
          .graph-export-actions { gap: 4px !important; }
          .graph-export-actions button { padding: 6px 7px !important; font-size: 11px !important; }
          .graph-hint { display: none; }
        }
      `}</style>
      {view === "home" && <HomePage onAnalyze={analyze} onOpenRepo={openReadyRepo} loading={loading} externalError={analysisError} onClearError={() => setAnalysisError("")} initialUrl={retryUrl} />}
      {view === "loading" && <LoadingPage repoName={repoName} stage={pollStage} />}
      {view === "dashboard" && data && <DashboardPage data={data} onReset={reset} />}
      {view === "error" && (
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "var(--bg)", textAlign: "center" }}>
          <div style={{ maxWidth: 480 }}>
            <h1 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: 32, fontWeight: 400, color: "var(--fg)", marginBottom: "1rem" }}>
              Analysis failed
            </h1>
            <p role="alert" style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, lineHeight: 1.6, color: "var(--muted)", marginBottom: "1.5rem" }}>
              {failureMessage}
            </p>
            <button
              type="button"
              onClick={reset}
              style={{ padding: "12px 20px", background: "var(--fg)", color: "var(--surface)", border: "none", borderRadius: 8, cursor: "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 500 }}
            >
              Try again
            </button>
          </div>
        </div>
      )}
    </>
  );
}
