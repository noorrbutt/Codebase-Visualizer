import { useState, useMemo } from "react";
import { getLangColor } from "../../utils/lang";

export default function FileListPanel({ nodes, edges, onSelectNode, selectedNode }) {
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("connections");
  const [langFilter, setLangFilter] = useState("all");

  const connCount = useMemo(() => {
    const map = {};
    nodes.forEach((n) => { map[n.path] = 0; });
    edges.forEach((e) => {
      if (map[e.source] !== undefined) map[e.source]++;
      if (map[e.target] !== undefined) map[e.target]++;
    });
    return map;
  }, [nodes, edges]);

  const langs = useMemo(
    () => ["all", ...new Set(nodes.map((n) => n.language).filter(Boolean))],
    [nodes]
  );

  const filtered = useMemo(
    () =>
      nodes
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
        }),
    [nodes, search, langFilter, sortBy, connCount]
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Toolbar */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid #F3F4F6",
          display: "flex",
          gap: 6,
          flexShrink: 0,
        }}
      >
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter files…"
          style={{
            flex: 1,
            border: "1px solid #E5E7EB",
            borderRadius: 6,
            padding: "5px 8px",
            fontFamily: "'DM Mono', monospace",
            fontSize: 11,
            outline: "none",
            background: "#FAFAF9",
            minWidth: 0,
          }}
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          style={{
            border: "1px solid #E5E7EB",
            borderRadius: 6,
            padding: "5px 6px",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 11,
            background: "#FAFAF9",
            cursor: "pointer",
          }}
        >
          <option value="connections">Most connected</option>
          <option value="lines">Most lines</option>
          <option value="name">Name A–Z</option>
        </select>
      </div>

      {/* Lang filter pills */}
      <div
        style={{
          padding: "6px 14px",
          borderBottom: "1px solid #F3F4F6",
          display: "flex",
          gap: 4,
          flexWrap: "wrap",
          flexShrink: 0,
        }}
      >
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

      {/* Count */}
      <div
        style={{
          padding: "5px 14px",
          borderBottom: "1px solid #F3F4F6",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: 10,
            color: "#9CA3AF",
          }}
        >
          {filtered.length} file{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* File rows */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.map((n) => {
          const conn = connCount[n.path] || 0;
          const filename = n.path.split("/").pop();
          const dir = n.path.includes("/")
            ? n.path.substring(0, n.path.lastIndexOf("/"))
            : "";
          const isSelected = selectedNode?.id === n.id;

          return (
            <div
              key={n.id}
              onClick={() => onSelectNode(n)}
              style={{
                padding: "8px 14px",
                borderBottom: "1px solid #F9FAFB",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: isSelected ? "#F9FAFB" : "transparent",
                borderLeft: isSelected ? "2px solid #111" : "2px solid transparent",
                transition: "background 0.12s",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) e.currentTarget.style.background = "#FAFAF9";
              }}
              onMouseLeave={(e) => {
                if (!isSelected) e.currentTarget.style.background = "transparent";
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: getLangColor(n.language),
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p
                  style={{
                    fontFamily: "'DM Mono', monospace",
                    fontSize: 11,
                    color: "#111",
                    margin: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {filename}
                </p>
                {dir && (
                  <p
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 10,
                      color: "#D1D5DB",
                      margin: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {dir}
                  </p>
                )}
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0, alignItems: "center" }}>
                {n.line_count > 0 && (
                  <span
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 10,
                      color: "#D1D5DB",
                    }}
                  >
                    {n.line_count}L
                  </span>
                )}
                {conn > 0 && (
                  <span
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 10,
                      color: "#9CA3AF",
                      background: "#F3F4F6",
                      borderRadius: 4,
                      padding: "1px 5px",
                    }}
                  >
                    {conn}↔
                  </span>
                )}
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <p
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              color: "#9CA3AF",
              textAlign: "center",
              margin: "24px 0",
            }}
          >
            No files match
          </p>
        )}
      </div>
    </div>
  );
}
