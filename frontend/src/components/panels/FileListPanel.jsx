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
    <div className="dashboard-file-list" style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Toolbar */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--border-soft)",
          display: "flex",
          gap: 6,
          flexShrink: 0,
        }}
      >
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter files…"
          aria-label="Filter files by path"
          style={{
            flex: 1,
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "5px 8px",
            fontFamily: "'DM Mono', monospace",
            fontSize: 11,
            outline: "none",
            background: "var(--input-bg)",
            color: "var(--fg)",
            minWidth: 0,
          }}
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          aria-label="Sort files"
          style={{
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "5px 6px",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 11,
            background: "var(--input-bg)",
            color: "var(--fg)",
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
          borderBottom: "1px solid var(--border-soft)",
          display: "flex",
          gap: 4,
          flexWrap: "wrap",
          flexShrink: 0,
        }}
      >
        {langs.map((l) => (
          <button
            key={l}
            type="button"
            aria-pressed={langFilter === l}
            onClick={() => setLangFilter(l)}
            style={{
              background: langFilter === l ? "var(--fg)" : "transparent",
              color: langFilter === l ? "var(--surface)" : "var(--muted)",
              border: `1px solid ${langFilter === l ? "var(--fg)" : "var(--border)"}`,
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
                  background: langFilter === l ? "var(--surface)" : getLangColor(l),
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
          borderBottom: "1px solid var(--border-soft)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: 10,
            color: "var(--muted)",
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
            <button
              key={n.id}
              type="button"
              aria-label={`Select ${n.path}`}
              aria-pressed={isSelected}
              onClick={() => onSelectNode(n)}
              style={{
                width: "100%",
                padding: "8px 14px",
                borderBottom: "1px solid var(--border-soft)",
                borderTop: 0,
                borderRight: 0,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: isSelected ? "var(--selected-bg)" : "transparent",
                borderLeft: isSelected ? "2px solid var(--fg)" : "2px solid transparent",
                transition: "background 0.12s",
                textAlign: "left",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) e.currentTarget.style.background = "var(--selected-hover)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = isSelected ? "var(--selected-bg)" : "transparent";
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
                    color: "var(--fg)",
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
                      color: "var(--muted)",
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
                      color: "var(--muted)",
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
                      color: "var(--muted)",
                      background: "var(--surface-soft)",
                      borderRadius: 4,
                      padding: "1px 5px",
                    }}
                  >
                    {conn}↔
                  </span>
                )}
              </div>
            </button>
          );
        })}
        {filtered.length === 0 && (
          <p
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              color: "var(--muted)",
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
