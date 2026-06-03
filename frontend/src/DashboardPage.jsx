import { useState, useEffect, useRef, useCallback } from "react";

const LANG_COLOR = {
  python: "#3B82F6",
  javascript: "#F59E0B",
  typescript: "#6366F1",
  css: "#8B5CF6",
  html: "#EF4444",
  markdown: "#6B7280",
  jsx: "#F59E0B",
  tsx: "#6366F1",
  default: "#9CA3AF",
};

function getLangColor(lang) {
  return LANG_COLOR[lang?.toLowerCase()] || LANG_COLOR.default;
}

// ── Stat card ──────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", letterSpacing: "0.05em", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: 26, color: accent || "#111", lineHeight: 1.1 }}>{value}</span>
      {sub && <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF" }}>{sub}</span>}
    </div>
  );
}

// ── Language donut chart (canvas) ──────────────────────────────────────
function LangDonut({ nodes }) {
  const canvasRef = useRef(null);

  const counts = {};
  nodes.forEach((n) => { counts[n.language || "unknown"] = (counts[n.language || "unknown"] || 0) + 1; });
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const legendTotal = entries.reduce((s, [, c]) => s + c, 0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 8, inner = r * 0.58;

    const ec = {};
    nodes.forEach((n) => { ec[n.language || "unknown"] = (ec[n.language || "unknown"] || 0) + 1; });
    const ent = Object.entries(ec).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const tot = ent.reduce((s, [, c]) => s + c, 0);

    ctx.clearRect(0, 0, W, H);
    let angle = -Math.PI / 2;
    ent.forEach(([lang, count]) => {
      const slice = (count / tot) * 2 * Math.PI;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, angle, angle + slice);
      ctx.closePath();
      ctx.fillStyle = getLangColor(lang);
      ctx.fill();
      angle += slice;
    });
    ctx.beginPath();
    ctx.arc(cx, cy, inner, 0, Math.PI * 2);
    ctx.fillStyle = "#FAFAF9";
    ctx.fill();
    ctx.font = "500 13px 'DM Sans', sans-serif";
    ctx.fillStyle = "#111";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(tot, cx, cy - 6);
    ctx.font = "11px 'DM Sans', sans-serif";
    ctx.fillStyle = "#9CA3AF";
    ctx.fillText("files", cx, cy + 10);
  }, [nodes]);

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      <canvas ref={canvasRef} width={110} height={110} style={{ flexShrink: 0 }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 5, flex: 1 }}>
        {entries.map(([lang, count]) => (
          <div key={lang} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: getLangColor(lang), flexShrink: 0 }} />
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#4B5563", flex: 1, textTransform: "capitalize" }}>{lang}</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#9CA3AF" }}>{((count / legendTotal) * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Complexity bar chart (canvas) ──────────────────────────────────────
function ComplexityChart({ nodes }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;

    const counts = { low: 0, medium: 0, high: 0, unknown: 0 };
    nodes.forEach((n) => {
      const c = n.ai_complexity?.toLowerCase();
      if (c === "low") counts.low++;
      else if (c === "medium") counts.medium++;
      else if (c === "high") counts.high++;
      else counts.unknown++;
    });
    const bars = [
      { label: "Low", count: counts.low, color: "#10B981" },
      { label: "Med", count: counts.medium, color: "#F59E0B" },
      { label: "High", count: counts.high, color: "#EF4444" },
      { label: "N/A", count: counts.unknown, color: "#E5E7EB" },
    ];
    const max = Math.max(...bars.map((b) => b.count), 1);
    const pad = 28, barW = (W - pad * 2) / bars.length;

    ctx.clearRect(0, 0, W, H);
    bars.forEach((b, i) => {
      const bh = ((b.count / max) * (H - 48)) || 2;
      const x = pad + i * barW + barW * 0.2;
      const bww = barW * 0.6;
      const y = H - 20 - bh;
      ctx.fillStyle = b.color;
      ctx.beginPath();
      ctx.roundRect(x, y, bww, bh, [3, 3, 0, 0]);
      ctx.fill();
      ctx.font = "11px 'DM Sans', sans-serif";
      ctx.fillStyle = "#9CA3AF";
      ctx.textAlign = "center";
      ctx.fillText(b.label, x + bww / 2, H - 4);
      if (b.count > 0) {
        ctx.fillStyle = "#4B5563";
        ctx.fillText(b.count, x + bww / 2, y - 5);
      }
    });
  }, [nodes]);

  return <canvas ref={canvasRef} width={180} height={120} style={{ width: "100%", height: 120 }} />;
}

// ── Connections histogram (canvas) ─────────────────────────────────────
function ConnectionsChart({ nodes, edges }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const connCount = {};
    nodes.forEach((n) => { connCount[n.path] = 0; });
    edges.forEach((e) => {
      if (connCount[e.source] !== undefined) connCount[e.source]++;
      if (connCount[e.target] !== undefined) connCount[e.target]++;
    });
    const vals = Object.values(connCount);
    const maxConn = Math.max(...vals, 1);
    const bins = new Array(8).fill(0);
    vals.forEach((v) => { bins[Math.min(Math.floor((v / (maxConn + 1)) * 8), 7)]++; });
    const maxBin = Math.max(...bins, 1);
    const barW = (W - 32) / 8;
    const pad = 16;

    bins.forEach((cnt, i) => {
      const bh = ((cnt / maxBin) * (H - 40)) || 2;
      const x = pad + i * barW + barW * 0.1;
      const bww = barW * 0.8;
      const y = H - 20 - bh;
      ctx.fillStyle = "#6366F1";
      ctx.globalAlpha = 0.6 + 0.4 * (i / 7);
      ctx.beginPath();
      ctx.roundRect(x, y, bww, bh, [2, 2, 0, 0]);
      ctx.fill();
      ctx.globalAlpha = 1;
    });

    ctx.font = "10px 'DM Mono', monospace";
    ctx.fillStyle = "#9CA3AF";
    ctx.textAlign = "center";
    ctx.fillText("0", pad + barW * 0.5, H - 4);
    ctx.fillText(maxConn, pad + barW * 7.5, H - 4);
  }, [nodes, edges]);

  return (
    <div>
      <canvas ref={canvasRef} width={220} height={100} style={{ width: "100%", height: 100 }} />
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "4px 0 0", textAlign: "center" }}>connections per file (0 → max)</p>
    </div>
  );
}

// ── Top connected files list ───────────────────────────────────────────
function TopFiles({ nodes, edges }) {
  const connCount = {};
  nodes.forEach((n) => { connCount[n.path] = 0; });
  edges.forEach((e) => {
    if (connCount[e.source] !== undefined) connCount[e.source]++;
    if (connCount[e.target] !== undefined) connCount[e.target]++;
  });
  const ranked = [...nodes].sort((a, b) => (connCount[b.path] || 0) - (connCount[a.path] || 0)).slice(0, 8);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {ranked.map((n, i) => {
        const conn = connCount[n.path] || 0;
        const maxConn = connCount[ranked[0].path] || 1;
        const pct = (conn / maxConn) * 100;
        const filename = n.path.split("/").pop();
        return (
          <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0", borderBottom: i < ranked.length - 1 ? "1px solid #F3F4F6" : "none" }}>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#D1D5DB", width: 14, textAlign: "right" }}>{i + 1}</span>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: getLangColor(n.language), flexShrink: 0 }} />
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#374151", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={n.path}>{filename}</span>
            <div style={{ width: 60, height: 4, background: "#F3F4F6", borderRadius: 2, flexShrink: 0 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: getLangColor(n.language), borderRadius: 2 }} />
            </div>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#9CA3AF", width: 18, textAlign: "right" }}>{conn}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── File list panel ────────────────────────────────────────────────────
function FileListPanel({ nodes, edges, onSelectNode }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("connections");
  const [langFilter, setLangFilter] = useState("all");

  const connCount = {};
  nodes.forEach((n) => { connCount[n.path] = 0; });
  edges.forEach((e) => {
    if (connCount[e.source] !== undefined) connCount[e.source]++;
    if (connCount[e.target] !== undefined) connCount[e.target]++;
  });

  const langs = ["all", ...new Set(nodes.map((n) => n.language).filter(Boolean))];

  const filtered = nodes
    .filter((n) => {
      const matchSearch = n.path.toLowerCase().includes(search.toLowerCase());
      const matchLang = langFilter === "all" || n.language === langFilter;
      return matchSearch && matchLang;
    })
    .sort((a, b) => {
      if (sortBy === "connections") return (connCount[b.path] || 0) - (connCount[a.path] || 0);
      if (sortBy === "lines") return (b.line_count || 0) - (a.line_count || 0);
      if (sortBy === "name") return a.path.localeCompare(b.path);
      return 0;
    });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid #F3F4F6", display: "flex", gap: 6, flexShrink: 0 }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter files…"
          style={{ flex: 1, border: "1px solid #E5E7EB", borderRadius: 6, padding: "5px 8px", fontFamily: "'DM Mono', monospace", fontSize: 11, outline: "none", background: "#FAFAF9", minWidth: 0 }}
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          style={{ border: "1px solid #E5E7EB", borderRadius: 6, padding: "5px 6px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, background: "#FAFAF9", cursor: "pointer" }}
        >
          <option value="connections">Most connected</option>
          <option value="lines">Most lines</option>
          <option value="name">Name A–Z</option>
        </select>
      </div>
      <div style={{ padding: "6px 12px", borderBottom: "1px solid #F3F4F6", display: "flex", gap: 4, flexWrap: "wrap", flexShrink: 0 }}>
        {langs.map((l) => (
          <button key={l} onClick={() => setLangFilter(l)} style={{ background: langFilter === l ? "#111" : "transparent", color: langFilter === l ? "#fff" : "#6B7280", border: `1px solid ${langFilter === l ? "#111" : "#E5E7EB"}`, borderRadius: 5, padding: "2px 7px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
            {l !== "all" && <span style={{ width: 5, height: 5, borderRadius: "50%", background: langFilter === l ? "#fff" : getLangColor(l) }} />}
            {l}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.map((n) => {
          const conn = connCount[n.path] || 0;
          const filename = n.path.split("/").pop();
          const dir = n.path.includes("/") ? n.path.substring(0, n.path.lastIndexOf("/")) : "";
          return (
            <div
              key={n.id}
              onClick={() => onSelectNode(n)}
              style={{ padding: "8px 12px", borderBottom: "1px solid #F9FAFB", cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "#F9FAFB"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: getLangColor(n.language), flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#111", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{filename}</p>
                {dir && <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#D1D5DB", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{dir}</p>}
              </div>
              <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center" }}>
                {n.line_count > 0 && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#D1D5DB" }}>{n.line_count}L</span>}
                {conn > 0 && <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#9CA3AF", background: "#F3F4F6", borderRadius: 4, padding: "1px 5px" }}>{conn}↔</span>}
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF", textAlign: "center", margin: "24px 0" }}>No files match</p>
        )}
      </div>
    </div>
  );
}

// ── Force graph (canvas) ───────────────────────────────────────────────
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
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    const nodeMap = {};
    simRef.current.forEach((n) => { nodeMap[n.id] = n; });

    // Build set of edge IDs connected to selected node
    const highlightedNodeIds = new Set();
    if (selectedNode) {
      highlightedNodeIds.add(selectedNode.id);
      edges.forEach((e) => {
        if (e.source === selectedNode.id || e.source === selectedNode.path) highlightedNodeIds.add(e.target);
        if (e.target === selectedNode.id || e.target === selectedNode.path) highlightedNodeIds.add(e.source);
      });
    }

    // Draw edges
    edges.forEach((e) => {
      const s = nodeMap[e.source], t = nodeMap[e.target];
      if (!s || !t) return;

      const isHighlighted = selectedNode && (
        e.source === selectedNode.id || e.source === selectedNode.path ||
        e.target === selectedNode.id || e.target === selectedNode.path
      );

      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = isHighlighted ? "rgba(99,102,241,0.7)" : "rgba(156,163,175,0.15)";
      ctx.lineWidth = isHighlighted ? 1.5 / scale : 0.8 / scale;
      ctx.stroke();
    });

    // Draw nodes — dimmed when something is selected and they're not connected
    simRef.current.forEach((n) => {
      const isSelected = selectedNode?.id === n.id;
      const isHovered = hoveredRef.current === n.id;
      const isConnected = highlightedNodeIds.has(n.id) || highlightedNodeIds.has(n.path);
      const isDimmed = selectedNode && !isSelected && !isConnected;

      // Bigger nodes: hub files (many imports) are visually larger
      const r = Math.max(5, Math.min(14, 5 + (n.import_count || 0) * 1.5));

      ctx.beginPath();
      ctx.arc(n.x, n.y, r / scale, 0, Math.PI * 2);
      ctx.fillStyle = getLangColor(n.language);
      ctx.globalAlpha = isDimmed ? 0.15 : isSelected ? 1 : isHovered ? 0.95 : 0.75;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isSelected || isHovered) {
        // Glow ring
        ctx.beginPath();
        ctx.arc(n.x, n.y, (r + 4) / scale, 0, Math.PI * 2);
        ctx.strokeStyle = getLangColor(n.language);
        ctx.lineWidth = 2 / scale;
        ctx.globalAlpha = isSelected ? 1 : 0.6;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Labels: always show for selected/hovered, show at higher zoom otherwise
      if (!isDimmed && (scale > 0.6 || isSelected || isHovered)) {
        const label = n.path.split("/").pop();
        ctx.font = `${isSelected ? "500 " : ""}${11 / scale}px 'DM Mono', monospace`;
        ctx.fillStyle = isSelected ? "#111" : isConnected ? "#374151" : "#9CA3AF";
        ctx.globalAlpha = isDimmed ? 0.1 : 1;
        ctx.fillText(label, n.x + (r + 4) / scale, n.y + 4 / scale);
        ctx.globalAlpha = 1;
      }
    });

    ctx.restore();
  }, [canvasRef, edges, selectedNode]);

  useEffect(() => {
    if (!nodes.length) return;
    const W = 1200, H = 900;
    const sim = nodes.map((n) => ({
      ...n, x: W / 2 + (Math.random() - 0.5) * 400, y: H / 2 + (Math.random() - 0.5) * 400, vx: 0, vy: 0,
    }));
    simRef.current = sim;
    const nodeMap = {};
    sim.forEach((n) => { nodeMap[n.id] = n; });
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
        s.vx += dx / d * f; s.vy += dy / d * f;
        t.vx -= dx / d * f; t.vy -= dy / d * f;
      });
      sim.forEach((n) => {
        if (n.fixed) return;
        n.vx *= 0.7; n.vy *= 0.7;
        n.x += n.vx; n.y += n.vy;
      });
      draw();
      animRef.current = requestAnimationFrame(step);
    };
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges, draw]);

  useEffect(() => { draw(); }, [selectedNode, draw]);

  const getNode = useCallback((ex, ey) => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return null;
    const rect = canvas.getBoundingClientRect();
    const { x, y, scale } = transformRef.current;
    const wx = (ex - rect.left - x) / scale;
    const wy = (ey - rect.top - y) / scale;
    return simRef.current.find((n) => {
      const r = Math.max(5, Math.min(14, 5 + (n.import_count || 0) * 1.5));
      return Math.hypot(n.x - wx, n.y - wy) <= r / scale + 4;
    }) || null;
  }, [canvasRef]);

  const onMouseDown = useCallback((e) => {
    const node = getNode(e.clientX, e.clientY);
    if (node) { dragNodeRef.current = node; node.fixed = true; }
    else { isDraggingRef.current = true; dragStartRef.current = { x: e.clientX - transformRef.current.x, y: e.clientY - transformRef.current.y }; }
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
  }, [canvasRef, draw, getNode]);

  const onMouseUp = useCallback(() => {
    if (dragNodeRef.current) {
      dragNodeRef.current.fixed = true;
      dragNodeRef.current = null;
    }
    isDraggingRef.current = false;
    dragStartRef.current = null;
  }, []);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const { x, y, scale } = transformRef.current;
    const newScale = Math.max(0.1, Math.min(4, scale * factor));
    transformRef.current = { x: mx - (mx - x) * (newScale / scale), y: my - (my - y) * (newScale / scale), scale: newScale };
    draw();
  }, [canvasRef, draw]);

  const onClick = useCallback((e) => {
    const node = getNode(e.clientX, e.clientY);
    onSelectNode(node);
  }, [getNode, onSelectNode]);

  return { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick };
}

// ── Node detail panel ──────────────────────────────────────────────────
function NodeDetail({ node, edges, onClose }) {
  if (!node) return null;

  const inbound = edges.filter((e) => e.target === node.id || e.target === node.path).length;
  const outbound = edges.filter((e) => e.source === node.id || e.source === node.path).length;

  return (
    <div style={{ width: 260, borderLeft: "1px solid #E5E7EB", background: "#fff", display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0 }}>
      <div style={{ padding: "10px 14px", borderBottom: "1px solid #F3F4F6", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", letterSpacing: "0.05em", textTransform: "uppercase" }}>File details</span>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 16, lineHeight: 1, padding: 2 }}>×</button>
      </div>
      <div style={{ padding: "10px 14px", borderBottom: "1px solid #F3F4F6" }}>
        <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: "#111", margin: "0 0 3px", wordBreak: "break-all" }}>{node.path.split("/").pop()}</p>
        <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#D1D5DB", margin: 0, wordBreak: "break-all" }}>{node.path}</p>
      </div>
      <div style={{ padding: "10px 14px", borderBottom: "1px solid #F3F4F6", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {[
          { label: "Language", value: node.language || "—" },
          { label: "Lines", value: node.line_count?.toLocaleString() || "0" },
          { label: "Imports", value: node.import_count || "0" },
          { label: "Complexity", value: node.ai_complexity || "—" },
          { label: "Inbound", value: inbound },
          { label: "Outbound", value: outbound },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "#F9FAFB", borderRadius: 6, padding: "7px 9px" }}>
            <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#9CA3AF", margin: "0 0 2px" }}>{label}</p>
            <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#111", margin: 0, textTransform: "capitalize" }}>{value}</p>
          </div>
        ))}
      </div>
      {node.ai_role && (
        <div style={{ padding: "10px 14px", borderBottom: "1px solid #F3F4F6" }}>
          <span style={{ display: "inline-block", background: "#F3F4F6", borderRadius: 5, padding: "3px 8px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#374151", textTransform: "capitalize" }}>
            {node.ai_role.replace(/_/g, " ")}
          </span>
        </div>
      )}
      {node.ai_summary && (
        <div style={{ padding: "10px 14px" }}>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#4B5563", lineHeight: 1.6, margin: 0 }}>{node.ai_summary}</p>
        </div>
      )}
    </div>
  );
}

// ── Main DashboardPage ─────────────────────────────────────────────────
export default function DashboardPage({ data, onReset }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedNode, setSelectedNode] = useState(null);
  const [langFilter, setLangFilter] = useState("all");
  const canvasRef = useRef(null);

  const filteredNodes = data.nodes.filter((n) => langFilter === "all" || n.language === langFilter);
  const filteredEdges = data.edges.filter((e) =>
    filteredNodes.find((n) => n.id === e.source || n.path === e.source) &&
    filteredNodes.find((n) => n.id === e.target || n.path === e.target)
  );

  const { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick } =
    useForceGraph(filteredNodes, filteredEdges, canvasRef, selectedNode, setSelectedNode);

  useEffect(() => {
    if (activeTab !== "graph") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => { canvas.width = canvas.offsetWidth; canvas.height = canvas.offsetHeight; };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [activeTab]);

  const totalLines = data.nodes.reduce((s, n) => s + (n.line_count || 0), 0);
  const connectedCount = new Set(data.edges.flatMap((e) => [e.source, e.target])).size;
  const langs = ["all", ...new Set(data.nodes.map((n) => n.language)).values()].filter(Boolean);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "graph", label: "Graph" },
    { id: "files", label: "Files" },
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#FAFAF9" }}>
      {/* Header */}
      <header style={{ height: 52, borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 1.25rem", background: "#fff", flexShrink: 0, zIndex: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={onReset} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 5, color: "#6B7280", fontFamily: "'DM Sans', sans-serif", fontSize: 13 }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            New
          </button>
          <span style={{ color: "#E5E7EB" }}>|</span>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#9CA3AF" }}>{data.owner}/{data.repo_name}</span>
          {data.status === "ready" && (
            <span style={{ background: "#F0FDF4", color: "#166534", fontSize: 11, fontFamily: "'DM Sans', sans-serif", padding: "2px 7px", borderRadius: 6 }}>ready</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setActiveTab(t.id)} style={{ background: activeTab === t.id ? "#F3F4F6" : "transparent", color: activeTab === t.id ? "#111" : "#6B7280", border: "none", borderRadius: 7, padding: "5px 12px", fontFamily: "'DM Sans', sans-serif", fontSize: 13, cursor: "pointer", fontWeight: activeTab === t.id ? 500 : 400 }}>
              {t.label}
            </button>
          ))}
        </div>
        <a href={`https://github.com/${data.owner}/${data.repo_name}`} target="_blank" rel="noreferrer" style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#6B7280", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }}>
          GitHub ↗
        </a>
      </header>

      {/* AI Summary — now a proper hero banner, not a grey footnote */}
      {data.summary && (
        <div style={{ borderBottom: "1px solid #E5E7EB", padding: "12px 1.25rem", background: "#fff", flexShrink: 0, display: "flex", alignItems: "flex-start", gap: 10 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "#F0F0FF", border: "1px solid #E0E0FF", borderRadius: 6, padding: "3px 8px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#6366F1", fontWeight: 500, flexShrink: 0, marginTop: 1 }}>
            ✦ AI
          </span>
          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: "#1F2937", margin: 0, lineHeight: 1.6 }}>
            {data.summary}
          </p>
        </div>
      )}

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 16 }}>
            <StatCard label="Total files" value={data.nodes.length.toLocaleString()} />
            <StatCard label="Connected files" value={connectedCount.toLocaleString()} sub={`${Math.round(connectedCount / data.nodes.length * 100)}% of codebase`} />
            <StatCard label="Dependencies" value={data.edges.length.toLocaleString()} sub="import connections" />
            <StatCard label="Total lines" value={totalLines > 999 ? `${(totalLines / 1000).toFixed(1)}k` : totalLines} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 10px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Languages</p>
              <LangDonut nodes={data.nodes} />
            </div>
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 10px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Complexity</p>
              <ComplexityChart nodes={data.nodes} />
            </div>
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 10px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Connections distribution</p>
              <ConnectionsChart nodes={data.nodes} edges={data.edges} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 10px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Most connected files</p>
              <TopFiles nodes={data.nodes} edges={data.edges} />
            </div>
            <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "14px 16px" }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: "0 0 10px", letterSpacing: "0.05em", textTransform: "uppercase" }}>File roles</p>
              {(() => {
                const roles = {};
                data.nodes.forEach((n) => {
                  if (!n.ai_role) return;
                  roles[n.ai_role] = (roles[n.ai_role] || 0) + 1;
                });
                const ent = Object.entries(roles).sort((a, b) => b[1] - a[1]);
                if (!ent.length) return <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF", margin: 0 }}>AI role analysis not yet available.</p>;
                return (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {ent.slice(0, 8).map(([role, count]) => (
                      <div key={role} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#4B5563", textTransform: "capitalize", flex: 1 }}>{role.replace(/_/g, " ")}</span>
                        <div style={{ width: 80, height: 4, background: "#F3F4F6", borderRadius: 2 }}>
                          <div style={{ width: `${(count / ent[0][1]) * 100}%`, height: "100%", background: "#6366F1", borderRadius: 2 }} />
                        </div>
                        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: "#9CA3AF", width: 18, textAlign: "right" }}>{count}</span>
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}

      {/* Graph tab */}
      {activeTab === "graph" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
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
            {/* Language filter */}
            <div style={{ position: "absolute", left: 12, bottom: 12, background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: "8px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#9CA3AF", margin: 0, letterSpacing: "0.06em" }}>LANGUAGE</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 8px", maxWidth: 240 }}>
                {langs.map((l) => (
                  <button key={l} onClick={() => setLangFilter(l)} style={{ background: langFilter === l ? "#111" : "transparent", color: langFilter === l ? "#fff" : "#6B7280", border: `1px solid ${langFilter === l ? "#111" : "#E5E7EB"}`, borderRadius: 5, padding: "2px 7px", fontFamily: "'DM Sans', sans-serif", fontSize: 11, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                    {l !== "all" && <span style={{ width: 5, height: 5, borderRadius: "50%", background: langFilter === l ? "#fff" : getLangColor(l) }} />}
                    {l}
                  </button>
                ))}
              </div>
            </div>
            {/* Hint */}
            <div style={{ position: "absolute", right: selectedNode ? 272 : 12, bottom: 12 }}>
              <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "#9CA3AF", margin: 0 }}>scroll to zoom · drag to pan · click node for details</p>
            </div>
            {/* Selected node name overlay */}
            {selectedNode && (
              <div style={{ position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)", background: "#fff", border: "1px solid #E5E7EB", borderRadius: 8, padding: "6px 14px", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: getLangColor(selectedNode.language), flexShrink: 0 }} />
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "#111" }}>{selectedNode.path.split("/").pop()}</span>
                <button onClick={() => setSelectedNode(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 14, padding: "0 0 0 4px", lineHeight: 1 }}>×</button>
              </div>
            )}
          </div>
          <NodeDetail node={selectedNode} edges={data.edges} onClose={() => setSelectedNode(null)} />
        </div>
      )}

      {/* Files tab */}
      {activeTab === "files" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <FileListPanel nodes={data.nodes} edges={data.edges} onSelectNode={setSelectedNode} />
          </div>
          <NodeDetail node={selectedNode} edges={data.edges} onClose={() => setSelectedNode(null)} />
        </div>
      )}
    </div>
  );
}