import { useState, useEffect, useRef } from "react";
import DashboardPage from "./DashboardPage";
import { API, getLangColor } from "./utils/lang";

function HomePage({ onAnalyze, loading, externalError, onClearError }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

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
      </div>
    </div>
  );
}


function LoadingPage({ repoName, status }) {
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d + 1) % 4), 400);
    return () => clearInterval(t);
  }, []);

  const steps = [
    { label: "Fetching repository tree", done: true },
    { label: "Reading source files", done: status !== "queued" },
    { label: "Parsing dependencies", done: status === "summarized" || status === "ready" },
    { label: "Generating AI summary", done: status === "summarized" || status === "ready" },
  ];

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
              <div style={{ width: 20, height: 20, borderRadius: "50%", background: s.done ? "#111827" : "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.3s" }}>
                {s.done
                  ? <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 5l2.5 2.5L8 3" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" /></svg>
                  : <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#D1D5DB" }} />
                }
              </div>
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: s.done ? "var(--fg)" : "var(--subtle)", transition: "color 0.3s" }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("home");
  const [loading, setLoading] = useState(false);
  const [repoName, setRepoName] = useState("");
  const [pollStatus, setPollStatus] = useState("queued");
  const [data, setData] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const pollRef = useRef(null);

  const analyze = async (url) => {
    setLoading(true);
    setView("loading");
    const parts = url.replace("https://github.com/", "").split("/");
    setRepoName(parts.slice(0, 2).join("/"));
    try {
      const res = await fetch(`${API}/repos/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: url }),
      });
      if (!res.ok) throw new Error("Analysis failed");
      const json = await res.json();
      setData(json);
      startPolling(json.id);
    } catch {
      // fetch or parse error — show message and return to home
      setLoading(false);
      setView("home");
      setAnalysisError("Could not connect to the backend. Make sure it's running on port 8000.");
    }
  };

  const startPolling = (id) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/repos/${id}`);
        const json = await res.json();
        setPollStatus(json.status);
        setData((prev) => ({ ...prev, summary: json.summary, status: json.status, nodes: json.nodes ?? prev.nodes, default_branch: json.default_branch ?? prev.default_branch }));
        if (json.status === "ready" || json.status === "failed") {
          clearInterval(pollRef.current);
          setLoading(false);
          setView("dashboard");
        }
      } catch {
        // polling error — will retry next interval
      }
    }, 3000);
  };

  useEffect(() => {
    if (data && view === "loading") {
      const timer = setTimeout(() => {
        clearInterval(pollRef.current);
        setLoading(false);
        setView("dashboard");
      }, 90000);
      return () => clearTimeout(timer);
    }
  }, [data, view]);

  const reset = () => {
    clearInterval(pollRef.current);
    setView("home");
    setData(null);
    setLoading(false);
    setRepoName("");
    setPollStatus("queued");
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
      {view === "home" && <HomePage onAnalyze={analyze} loading={loading} externalError={analysisError} onClearError={() => setAnalysisError("")} />}
      {view === "loading" && <LoadingPage repoName={repoName} status={pollStatus} />}
      {view === "dashboard" && data && <DashboardPage data={data} onReset={reset} />}
    </>
  );
}
