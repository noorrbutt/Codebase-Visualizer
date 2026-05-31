import { useState, useEffect, useRef, useCallback } from "react";

const API = "http://127.0.0.1:8000";

const LANG_COLOR = {
  python: "#3B82F6",
  javascript: "#F59E0B",
  typescript: "#3B82F6",
  css: "#8B5CF6",
  html: "#EF4444",
  markdown: "#6B7280",
  default: "#9CA3AF",
};

function getLangColor(lang) {
  return LANG_COLOR[lang?.toLowerCase()] || LANG_COLOR.default;
}

function useForceGraph(nodes, edges, canvasRef, selectedNode, onSelectNode) {
  const simRef = useRef(null);
  const animRef = useRef(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef(null);
  const dragNodeRef = useRef(null);
  const hoveredRef = useRef(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return;
    const ctx = canvas.getContext("2d");
    const { x, y, scale } = transformRef.current;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    const nodeMap = {};
    simRef.current.forEach((n) => { nodeMap[n.id] = n; });

    edges.forEach((e) => {
      const s = nodeMap[e.source];
      const t = nodeMap[e.target];
      if (!s || !t) return;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = "rgba(156,163,175,0.3)";
      ctx.lineWidth = 1 / scale;
      ctx.stroke();

      const angle = Math.atan2(t.y - s.y, t.x - s.x);
      const r = 6;
      const ax = t.x - r * Math.cos(angle);
      const ay = t.y - r * Math.sin(angle);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - 6 / scale * Math.cos(angle - 0.4), ay - 6 / scale * Math.sin(angle - 0.4));
      ctx.lineTo(ax - 6 / scale * Math.cos(angle + 0.4), ay - 6 / scale * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fillStyle = "rgba(156,163,175,0.4)";
      ctx.fill();
    });

    simRef.current.forEach((n) => {
      const isSelected = selectedNode?.id === n.id;
      const isHovered = hoveredRef.current === n.id;
      const r = Math.max(4, Math.min(10, 4 + n.import_count));

      ctx.beginPath();
      ctx.arc(n.x, n.y, r / scale, 0, Math.PI * 2);
      ctx.fillStyle = getLangColor(n.language);
      ctx.globalAlpha = isSelected ? 1 : isHovered ? 0.9 : 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, (r + 3) / scale, 0, Math.PI * 2);
        ctx.strokeStyle = getLangColor(n.language);
        ctx.lineWidth = 1.5 / scale;
        ctx.stroke();
      }

      if (scale > 0.6 || isSelected || isHovered) {
        const label = n.path.split("/").pop();
        ctx.font = `${11 / scale}px 'DM Mono', monospace`;
        ctx.fillStyle = isSelected ? "#111" : "#6B7280";
        ctx.fillText(label, n.x + (r + 3) / scale, n.y + 4 / scale);
      }
    });

    ctx.restore();
  }, [nodes, edges, selectedNode]);

  useEffect(() => {
    if (!nodes.length) return;

    const W = 1200, H = 900;
    const sim = nodes.map((n, i) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 400,
      y: H / 2 + (Math.random() - 0.5) * 400,
      vx: 0, vy: 0,
    }));
    simRef.current = sim;

    const nodeMap = {};
    sim.forEach((n) => { nodeMap[n.id] = n; });

    const edgeMap = {};
    edges.forEach((e) => {
      if (!edgeMap[e.source]) edgeMap[e.source] = [];
      if (!edgeMap[e.target]) edgeMap[e.target] = [];
      edgeMap[e.source].push(e.target);
      edgeMap[e.target].push(e.source);
    });

    let tick = 0;
    const step = () => {
      tick++;
      const alpha = Math.max(0.001, 0.3 * Math.pow(0.995, tick));
      const cx = W / 2, cy = H / 2;

      sim.forEach((a) => {
        a.vx += (cx - a.x) * 0.001 * alpha;
        a.vy += (cy - a.y) * 0.001 * alpha;

        sim.forEach((b) => {
          if (a.id === b.id) return;
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const rep = 800 / (d * d);
          a.vx += dx * rep * alpha;
          a.vy += dy * rep * alpha;
        });
      });

      edges.forEach((e) => {
        const s = nodeMap[e.source], t = nodeMap[e.target];
        if (!s || !t) return;
        const dx = t.x - s.x, dy = t.y - s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const ideal = 80, f = (d - ideal) * 0.03 * alpha;
        s.vx += dx / d * f;
        s.vy += dy / d * f;
        t.vx -= dx / d * f;
        t.vy -= dy / d * f;
      });

      sim.forEach((n) => {
        if (n.fixed) return;
        n.vx *= 0.7;
        n.vy *= 0.7;
        n.x += n.vx;
        n.y += n.vy;
      });

      draw();
      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges]);

  useEffect(() => { draw(); }, [selectedNode, draw]);

  const getNode = useCallback((ex, ey) => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return null;
    const rect = canvas.getBoundingClientRect();
    const { x, y, scale } = transformRef.current;
    const wx = (ex - rect.left - x) / scale;
    const wy = (ey - rect.top - y) / scale;
    return simRef.current.find((n) => {
      const r = Math.max(4, Math.min(10, 4 + n.import_count));
      return Math.hypot(n.x - wx, n.y - wy) <= r / scale + 4;
    }) || null;
  }, []);

  const onMouseDown = useCallback((e) => {
    const node = getNode(e.clientX, e.clientY);
    if (node) {
      dragNodeRef.current = node;
      node.fixed = true;
    } else {
      isDraggingRef.current = true;
      dragStartRef.current = { x: e.clientX - transformRef.current.x, y: e.clientY - transformRef.current.y };
    }
  }, [getNode]);

  const onMouseMove = useCallback((e) => {
    if (dragNodeRef.current) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const { x, y, scale } = transformRef.current;
      dragNodeRef.current.x = (e.clientX - rect.left - x) / scale;
      dragNodeRef.current.y = (e.clientY - rect.top - y) / scale;
      draw();
    } else if (isDraggingRef.current) {
      transformRef.current.x = e.clientX - dragStartRef.current.x;
      transformRef.current.y = e.clientY - dragStartRef.current.y;
      draw();
    } else {
      const node = getNode(e.clientX, e.clientY);
      const canvas = canvasRef.current;
      if (canvas) canvas.style.cursor = node ? "pointer" : "grab";
      const prev = hoveredRef.current;
      hoveredRef.current = node?.id || null;
      if (prev !== hoveredRef.current) draw();
    }
  }, [draw, getNode]);

  const onMouseUp = useCallback((e) => {
    if (dragNodeRef.current) {
      const moved = Math.hypot(dragNodeRef.current.vx, dragNodeRef.current.vy) < 2;
      if (moved) onSelectNode(dragNodeRef.current);
      dragNodeRef.current.fixed = true;
      dragNodeRef.current = null;
    }
    isDraggingRef.current = false;
    dragStartRef.current = null;
  }, [onSelectNode]);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const { x, y, scale } = transformRef.current;
    const newScale = Math.max(0.1, Math.min(4, scale * factor));
    transformRef.current = {
      x: mx - (mx - x) * (newScale / scale),
      y: my - (my - y) * (newScale / scale),
      scale: newScale,
    };
    draw();
  }, [draw]);

  const onClick = useCallback((e) => {
    if (!dragNodeRef.current) {
      const node = getNode(e.clientX, e.clientY);
      onSelectNode(node);
    }
  }, [getNode, onSelectNode]);

  return { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick };
}

function HomePage({ onAnalyze, loading }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    if (!url.trim()) return setError("Paste a GitHub URL to get started.");
    if (!url.includes("github.com/")) return setError("Must be a github.com URL.");
    onAnalyze(url.trim());
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "#FAFAF9" }}>
      <div style={{ maxWidth: 560, width: "100%", textAlign: "center" }}>
        <div style={{ marginBottom: "2.5rem" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: "1.5rem" }}>
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
              <circle cx="5" cy="5" r="3" fill="#111" />
              <circle cx="17" cy="5" r="3" fill="#111" />
              <circle cx="11" cy="17" r="3" fill="#111" />
              <line x1="5" y1="5" x2="17" y2="5" stroke="#111" strokeWidth="1.5" />
              <line x1="5" y1="5" x2="11" y2="17" stroke="#111" strokeWidth="1.5" />
              <line x1="17" y1="5" x2="11" y2="17" stroke="#111" strokeWidth="1.5" />
            </svg>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, fontWeight: 500, letterSpacing: "0.06em", color: "#111" }}>CODEBASE VISUALIZER</span>
          </div>
          <h1 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "clamp(2rem, 5vw, 3rem)", fontWeight: 400, lineHeight: 1.15, color: "#111", margin: "0 0 1rem" }}>
            See how your code<br />connects.
          </h1>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 16, color: "#6B7280", lineHeight: 1.6, margin: 0 }}>
            Paste any public GitHub repository and get an interactive dependency graph in seconds.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", gap: 0, border: "1.5px solid #E5E7EB", borderRadius: 10, overflow: "hidden", background: "#fff", transition: "border-color 0.15s", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              disabled={loading}
              style={{ flex: 1, border: "none", outline: "none", padding: "14px 16px", fontFamily: "'DM Mono', monospace", fontSize: 13, color: "#111", background: "transparent", minWidth: 0 }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{ padding: "14px 24px", background: "#111", color: "#fff", border: "none", cursor: loading ? "not-allowed" : "pointer", fontFamily: "'DM Sans', sans-serif", fontSize: 14, fontWeight: 500, whiteSpace: "nowrap", opacity: loading ? 0.6 : 1, transition: "background 0.15s" }}
            >
              {loading ? "Analyzing…" : "Visualize →"}
            </button>
          </div>
          {error && <p style={{ margin: "8px 0 0", fontSize: 13, color: "#EF4444", fontFamily: "'DM Sans', sans-serif" }}>{error}</p>}
        </form>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 24, flexWrap: "wrap" }}>
          {["Python", "JavaScript", "TypeScript", "HTML/CSS"].map((l) => (
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
    { label: "Parsing dependencies", done: status === "ready" || status === "failed" },
    { label: "Generating AI summary", done: status === "ready" },
  ];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem", background: "#FAFAF9" }}>
      <div style={{ maxWidth: 400, width: "100%", textAlign: "center" }}>
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ width: 48, height: 48, margin: "0 auto 1.5rem", position: "relative" }}>
            <svg width="48" height="48" viewBox="0 0 48 48" style={{ animation: "spin 2s linear infinite" }}>
              <circle cx="24" cy="24" r="20" fill="none" stroke="#E5E7EB" strokeWidth="3" />
              <circle cx="24" cy="24" r="20" fill="none" stroke="#111" strokeWidth="3" strokeDasharray="30 96" strokeLinecap="round" />
            </svg>
          </div>
          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#9CA3AF", letterSpacing: "0.08em", margin: "0 0 0.5rem" }}>ANALYZING</p>
          <h2 style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: 22, fontWeight: 400, color: "#111", margin: "0 0 2rem" }}>
            {repoName || "repository"}{".".repeat(dots)}
          </h2>
        </div>

        <div style={{ textAlign: "left" }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: i < steps.length - 1 ? "1px solid #F3F4F6" : "none" }}>
              <div style={{ width: 20, height: 20, borderRadius: "50%", background: s.done ? "#111" : "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.3s" }}>
                {s.done
                  ? <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 5l2.5 2.5L8 3" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" /></svg>
                  : <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#D1D5DB" }} />
                }
              </div>
              <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: s.done ? "#111" : "#9CA3AF", transition: "color 0.3s" }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );
}

function Legend({ nodes }) {
  const langs = [...new Set(nodes.map((n) => n.language))].filter(Boolean);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px" }}>
      {langs.map((l) => (
        <span key={l} style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#6B7280" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: getLangColor(l) }} />
          {l}
        </span>
      ))}
    </div>
  );
}

function NodePanel({ node, onClose }) {
  if (!node) return null;
  return (
    <div style={{ position: "absolute", right: 16, top: 16, width: 280, background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12, padding: "1.25rem", boxShadow: "0 4px 16px rgba(0,0,0,0.08)", zIndex: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#9CA3AF", margin: "0 0 4px", letterSpacing: "0.06em" }}>FILE</p>
          <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#111", margin: 0, wordBreak: "break-all", lineHeight: 1.5 }}>{node.path}</p>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 18, lineHeight: 1, padding: "0 0 0 8px", flexShrink: 0 }}>×</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: "1rem" }}>
        {[
          { label: "Language", value: node.language || "—" },
          { label: "Lines", value: node.line_count?.toLocaleString() || "0" },
          { label: "Imports", value: node.import_count || "0" },
          { label: "Complexity", value: node.ai_complexity || "—" },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "#F9FAFB", borderRadius: 8, padding: "8px 10px" }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 2px" }}>{label}</p>
            <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: "#111", margin: 0, textTransform: "capitalize" }}>{value}</p>
          </div>
        ))}
      </div>

      {node.ai_role && (
        <div style={{ marginBottom: "0.75rem" }}>
          <span style={{ display: "inline-block", background: "#F3F4F6", borderRadius: 6, padding: "3px 8px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#374151", textTransform: "capitalize" }}>
            {node.ai_role.replace(/_/g, " ")}
          </span>
        </div>
      )}

      {node.ai_summary && (
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#4B5563", lineHeight: 1.6, margin: 0 }}>{node.ai_summary}</p>
      )}
    </div>
  );
}

function GraphPage({ data, repoUrl, onReset }) {
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("all");
  const [showAllFiles, setShowAllFiles] = useState(false);
  const canvasRef = useRef(null);

  const connectedPaths = new Set(data.edges.flatMap((e) => [e.source, e.target]));
  const connectedNodes = data.nodes.filter((n) => connectedPaths.has(n.path));
  const visibleNodes = showAllFiles ? data.nodes : connectedNodes;

  const filteredNodes = visibleNodes.filter((n) =>
    filter === "all" ? true : n.language === filter
  );
  const filteredEdges = data.edges.filter((e) =>
    filteredNodes.find((n) => n.id === e.source || n.path === e.source) &&
    filteredNodes.find((n) => n.id === e.target || n.path === e.target)
  );

  const { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick } =
    useForceGraph(filteredNodes, filteredEdges, canvasRef, selected, setSelected);

  const langs = ["all", ...new Set(data.nodes.map((n) => n.language)).values()].filter(Boolean);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#FAFAF9" }}>
      <header style={{ height: 52, borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 1.25rem", background: "#fff", flexShrink: 0, zIndex: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={onReset} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 6, color: "#6B7280", fontFamily: "'DM Sans', sans-serif", fontSize: 13 }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            New
          </button>
          <span style={{ color: "#E5E7EB" }}>|</span>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#9CA3AF" }}>
            {data.owner}/{data.repo_name}
          </span>
          {data.status === "ready" && (
            <span style={{ background: "#F0FDF4", color: "#166534", fontSize: 11, fontFamily: "'DM Sans', sans-serif", padding: "2px 7px", borderRadius: 6 }}>ready</span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF" }}>{filteredNodes.length} files · {filteredEdges.length} connections</span>
          <button
            onClick={() => setShowAllFiles((prev) => !prev)}
            style={{
              background: showAllFiles ? "#111" : "transparent",
              color: showAllFiles ? "#fff" : "#6B7280",
              border: `1px solid ${showAllFiles ? "#111" : "#E5E7EB"}`,
              borderRadius: 8,
              padding: "6px 10px",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            {showAllFiles ? "Show connected only" : "Show all files"}
          </button>
        </div>
      </header>

      {data.summary && (
        <div style={{ borderBottom: "1px solid #F3F4F6", padding: "10px 1.25rem", background: "#fff", flexShrink: 0 }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, color: "#4B5563", margin: 0, lineHeight: 1.5 }}>
            <span style={{ color: "#9CA3AF", marginRight: 8 }}>AI Summary</span>
            {data.summary}
          </p>
        </div>
      )}

      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%", cursor: "grab", display: "block" }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onWheel={onWheel}
          onClick={onClick}
        />

        <div style={{ position: "absolute", left: 16, bottom: 16, background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "10px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: 0, letterSpacing: "0.06em" }}>LANGUAGE</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 12px", maxWidth: 260 }}>
            {langs.map((l) => (
              <button key={l} onClick={() => setFilter(l)} style={{ background: filter === l ? "#111" : "transparent", color: filter === l ? "#fff" : "#6B7280", border: `1px solid ${filter === l ? "#111" : "#E5E7EB"}`, borderRadius: 6, padding: "3px 8px", fontFamily: "'DM Sans', sans-serif", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 5, transition: "all 0.15s" }}>
                {l !== "all" && <span style={{ width: 6, height: 6, borderRadius: "50%", background: filter === l ? "#fff" : getLangColor(l) }} />}
                {l}
              </button>
            ))}
          </div>
        </div>

        <div style={{ position: "absolute", right: 16, bottom: 16, display: "flex", gap: 8 }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: 0, alignSelf: "center" }}>scroll to zoom · drag to pan · click node for details</p>
        </div>

        <NodePanel node={selected} onClose={() => setSelected(null)} />
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("home");
  const [loading, setLoading] = useState(false);
  const [repoName, setRepoName] = useState("");
  const [pollStatus, setPollStatus] = useState("queued");
  const [data, setData] = useState(null);
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
    } catch (err) {
      setLoading(false);
      setView("home");
      alert("Could not connect to the backend. Make sure it's running on port 8000.");
    }
  };

  const startPolling = (id) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/repos/${id}`);
        const json = await res.json();
        setPollStatus(json.status);
        if (json.summary) {
          setData((prev) => ({ ...prev, summary: json.summary, status: json.status }));
        }
        if (json.status === "ready" || json.status === "failed") {
          clearInterval(pollRef.current);
          setLoading(false);
          setView("graph");
        }
      } catch {}
    }, 3000);
  };

  useEffect(() => {
    if (data && view === "loading") {
      const timer = setTimeout(() => {
        if (view === "loading") {
          clearInterval(pollRef.current);
          setLoading(false);
          setView("graph");
        }
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
        body { background: #FAFAF9; }
        button:focus-visible { outline: 2px solid #111; outline-offset: 2px; }
        input:focus { border-color: #111 !important; }
      `}</style>
      {view === "home" && <HomePage onAnalyze={analyze} loading={loading} />}
      {view === "loading" && <LoadingPage repoName={repoName} status={pollStatus} />}
      {view === "graph" && data && <GraphPage data={data} onReset={reset} />}
    </>
  );
}