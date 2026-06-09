import { useRef, useEffect, useState } from "react";
import { useForceGraph } from "../../hooks/useForceGraph";
import { getLangColor } from "../../utils/lang";

export default function GraphView({ nodes, edges, selectedNode, onSelectNode }) {
  const canvasRef = useRef(null);
  const [langFilter, setLangFilter] = useState("all");

  const filteredNodes = langFilter === "all"
    ? nodes
    : nodes.filter((n) => n.language === langFilter);

  const filteredEdges = langFilter === "all"
    ? edges
    : edges.filter(
        (e) =>
          filteredNodes.find((n) => n.path === e.source) &&
          filteredNodes.find((n) => n.path === e.target)
      );

  const { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick } = useForceGraph(
    filteredNodes,
    filteredEdges,
    canvasRef,
    selectedNode,
    onSelectNode
  );

  const langs = ["all", ...new Set(nodes.map((n) => n.language).filter(Boolean))];

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
          LANGUAGE
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 8px", maxWidth: 240 }}>
          {langs.map((l) => (
            <button
              key={l}
              onClick={() => setLangFilter(l)}
              style={{
                background: langFilter === l ? "#111" : "transparent",
                color: langFilter === l ? "#fff" : "#6B7280",
                border: `1px solid ${langFilter === l ? "#111" : "#E5E7EB"}`,
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
              {l !== "all" && (
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: langFilter === l ? "#fff" : getLangColor(l),
                  }}
                />
              )}
              {l}
            </button>
          ))}
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
        scroll to zoom · drag to pan · click node
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
