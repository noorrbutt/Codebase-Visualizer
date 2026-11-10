import { useRef, useEffect, useMemo, useState } from "react";
import { useForceGraph } from "../../hooks/useForceGraph";
import { getLangColor } from "../../utils/lang";

export default function GraphView({ nodes, edges, selectedNode, onSelectNode }) {
  const canvasRef = useRef(null);
  const [hiddenLanguages, setHiddenLanguages] = useState(() => new Set());
  const [search, setSearch] = useState("");
  const [neighborhoodOnly, setNeighborhoodOnly] = useState(false);
  const langs = useMemo(
    () => [...new Set(nodes.map((node) => node.language || "Unknown"))].sort(),
    [nodes],
  );
  const matchingPaths = useMemo(
    () => nodes
      .filter((node) => node.path.toLowerCase().includes(search.trim().toLowerCase()))
      .map((node) => node.path),
    [nodes, search],
  );
  const visiblePaths = useMemo(
    () => new Set(
      nodes
        .filter((node) => !hiddenLanguages.has(node.language || "Unknown"))
        .map((node) => node.path),
    ),
    [nodes, hiddenLanguages],
  );
  const {
    onMouseDown,
    onMouseMove,
    onMouseUp,
    onWheel,
    onClick,
    centerNode,
  } = useForceGraph(
    nodes,
    edges,
    canvasRef,
    selectedNode,
    onSelectNode,
    { visiblePaths, searchQuery: search, neighborhoodOnly },
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      const { width, height } = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const pixelWidth = Math.round(width * dpr);
      const pixelHeight = Math.round(height * dpr);
      if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
      if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
      canvas.getContext("2d").setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    window.addEventListener("resize", resize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, []);

  const handleSearchKeyDown = (event) => {
    if (event.key !== "Enter") return;
    const firstMatch = matchingPaths.find((path) => visiblePaths.has(path));
    if (!firstMatch) return;
    const node = nodes.find((item) => item.path === firstMatch);
    if (node) {
      onSelectNode(node);
      centerNode(firstMatch);
    }
  };

  const toggleLanguage = (language) => {
    setHiddenLanguages((hidden) => {
      const next = new Set(hidden);
      if (next.has(language)) next.delete(language);
      else next.add(language);
      return next;
    });
  };

  return (
    <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", zIndex: 2, top: 12, left: 12, display: "flex", flexDirection: "column", gap: 8, width: "min(360px, calc(100% - 24px))" }}>
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={handleSearchKeyDown}
          placeholder="Search files by path…"
          aria-label="Search files by path"
          style={{ width: "100%", padding: "9px 12px", border: "1px solid #E5E7EB", borderRadius: 8, background: "#fff", fontFamily: "'DM Sans', sans-serif", fontSize: 13, boxShadow: "0 1px 6px rgba(0,0,0,0.06)" }}
        />
        {selectedNode && (
          <label style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 7, padding: "6px 9px", border: "1px solid #E5E7EB", borderRadius: 7, background: "#fff", color: "#4B5563", fontFamily: "'DM Sans', sans-serif", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={neighborhoodOnly}
              onChange={(event) => setNeighborhoodOnly(event.target.checked)}
            />
            Neighborhood only
          </label>
        )}
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", cursor: "grab", display: "block" }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onWheel={onWheel}
        onClick={onClick}
      />

      {/* Language visibility */}
      <div
        style={{
          position: "absolute",
          left: 12,
          bottom: 14,
          background: "#fff",
          border: "1px solid #E5E7EB",
          borderRadius: 8,
          padding: "8px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
          boxShadow: "0 1px 6px rgba(0,0,0,0.06)",
        }}
      >
        <p
          style={{
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 10,
            color: "#9CA3AF",
            margin: 0,
            letterSpacing: "0.06em",
          }}
        >
          VISIBLE LANGUAGES
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 8px", maxWidth: 240 }}>
          {langs.map((l) => {
            const visible = !hiddenLanguages.has(l);
            return (
            <button
              key={l}
              type="button"
              aria-pressed={visible}
              onClick={() => toggleLanguage(l)}
              style={{
                background: visible ? "#111" : "transparent",
                color: visible ? "#fff" : "#6B7280",
                border: `1px solid ${visible ? "#111" : "#E5E7EB"}`,
                borderRadius: 5,
                padding: "2px 7px",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 11,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: visible ? "#fff" : getLangColor(l) }} />
              {l}
            </button>
            );
          })}
        </div>
      </div>

      {/* Hint */}
      <p
        style={{
          position: "absolute",
          right: 14,
          bottom: 14,
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 11,
          color: "#9CA3AF",
          margin: 0,
        }}
      >
        scroll to zoom · drag to pan · click node · Enter to focus search
      </p>

      {/* Selected node overlay */}
      {selectedNode && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "#fff",
            border: "1px solid #E5E7EB",
            borderRadius: 8,
            padding: "6px 14px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 2px 8px rgba(0,0,0,0.07)",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: getLangColor(selectedNode.language),
            }}
          />
          <span
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 12,
              color: "#111",
            }}
          >
            {selectedNode.path.split("/").pop()}
          </span>
          <button
            onClick={() => onSelectNode(null)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "#9CA3AF",
              fontSize: 14,
              padding: "0 0 0 4px",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
