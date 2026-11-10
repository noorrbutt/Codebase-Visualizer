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
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "var(--bg)", backgroundImage: "radial-gradient(#E5E7EB 1px, transparent 1px)", backgroundSize: "24px 24px" }}>
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
          <div style={{ display: "flex", gap: 0, border: "1.5px solid var(--border)", borderRadius: 10, overflow: "hidden", background: "var(--surface)", transition: "border-color 0.15s", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
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
          {errorMessage && <p style={{ margin: "8px 0 0", fontSize: 13, color: "#EF4444", fontFamily: "'DM Sans', sans-serif" }}>{errorMessage}</p>}
        </form>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 24, flexWrap: "wrap" }}>
          {['Python', 'JavaScript', 'TypeScript', 'HTML/CSS'].map((l) => (
            <span key={l} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF", display: "flex", alignItems: "center", gap: 5 }}>
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
          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#9CA3AF", letterSpacing: "0.08em", margin: "0 0 0.5rem" }}>ANALYZING</p>
          <h2 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: 22, fontWeight: 400, color: "var(--fg)", margin: "0 0 2rem" }}>
            {repoName || "repository"}{"...".slice(0, dots + 1)}
          </h2>
        </div>
        <div style={{ textAlign: "left" }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: i < steps.length - 1 ? "1px solid var(--border)" : "none" }}>
              <div style={{ width: 20, height: 20, borderRadius: "50%", background: s.done || s.active ? "#111827" : "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.3s" }}>
                {s.done
                  ? <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 5l2.5 2.5L8 3" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" /></svg>
                  : <div style={{ width: 6, height: 6, borderRadius: "50%", background: s.active ? "#fff" : "#D1D5DB" }} />
                }
              </div>
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: s.done || s.active ? "var(--fg)" : "var(--subtle)", transition: "color 0.3s" }}>{s.label}</span>
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
          --bg: #F8F9FA;
          --surface: #FFFFFF;
          --border: #E5E7EB;
          --fg: #111827;
          --fg-dim: #374151;
          --muted: #6B7280;
          --subtle: #9CA3AF;
          --accent-blue: #3B82F6;
          --accent-green: #10B981;
          --accent-purple: #8B5CF6;
          --accent-amber: #F59E0B;
        }
        body { background: var(--bg); color: var(--fg); }
        button:focus-visible { outline: 2px solid var(--fg); outline-offset: 2px; }
        input:focus { border-color: var(--fg) !important; }
        ::-webkit-scrollbar-thumb { background: #E5E7EB; }
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
