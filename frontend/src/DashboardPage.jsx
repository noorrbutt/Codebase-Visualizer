import { useEffect, useRef, useState } from "react";
import LangDonut from "./components/charts/LangDonut";
import ComplexityChart from "./components/charts/ComplexityChart";
import ConnectionsChart from "./components/charts/ConnectionsChart";
import TopFiles from "./components/charts/TopFiles";
import FileRoles from "./components/charts/FileRoles";
import GraphView from "./components/graph/GraphView";
import FileListPanel from "./components/panels/FileListPanel";
import NodeDetail from "./components/panels/NodeDetail";
import { copyMermaidGraph, exportGraphJson, exportGraphPng } from "./utils/export";

function StatCard({ label, value, sub, icon, tint }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "18px 20px",
        display: "flex",
        alignItems: "center",
        gap: 14,
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          background: tint.bg,
          color: tint.fg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
        <span
          style={{
            fontFamily: "'Instrument Serif', Georgia, serif",
            fontSize: 26,
            color: "var(--fg)",
            lineHeight: 1.1,
          }}
        >
          {value}
        </span>
        <span
          style={{
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 12,
            color: "var(--muted)",
          }}
        >
          {label}
        </span>
        {sub && (
          <span
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 11,
              color: "var(--muted)",
            }}
          >
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

const ICONS = {
  files: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M14 3v5h5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  ),
  link: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M9 15l6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M10 6.5l1-1a4 4 0 0 1 5.7 5.7l-1.4 1.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M14 17.5l-1 1a4 4 0 0 1-5.7-5.7l1.4-1.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  deps: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="6" cy="6" r="2.5" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="18" cy="6" r="2.5" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="18" r="2.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8 7.5L11 16M16 7.5L13 16M8.5 6h7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  lines: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  cycles: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M7 7h5a5 5 0 0 1 0 10h-1M7 7l3-3M7 7l3 3M17 17h-5a5 5 0 0 1 0-10h1m4 10-3-3m3 3-3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  orphans: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="7" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 9v6m-3-3h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
};

function MetricPathList({ title, items, onSelectPath, formatItem = (item) => item.path }) {
  return (
    <div style={{ minWidth: 0 }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: 600, color: "var(--muted)", letterSpacing: "0.06em", textTransform: "uppercase", margin: "0 0 8px" }}>
        {title}
      </p>
      {items.length > 0 ? items.map((item) => {
        const path = typeof item === "string" ? item : item.path;
        return (
          <button
            key={path}
            type="button"
            onClick={() => onSelectPath(path)}
            style={{ display: "flex", justifyContent: "space-between", width: "100%", gap: 8, padding: "5px 0", border: 0, background: "transparent", color: "var(--fg-dim)", cursor: "pointer", textAlign: "left", fontFamily: "'DM Mono', monospace", fontSize: 11 }}
            title={`Select ${path} in graph`}
          >
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{formatItem(typeof item === "string" ? { path: item } : item)}</span>
            {typeof item !== "string" && <span style={{ color: "var(--muted)", flexShrink: 0 }}>{item.count}</span>}
          </button>
        );
      }) : (
        <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)", margin: 0 }}>None</p>
      )}
    </div>
  );
}

function ArchitectureMetrics({ metrics, onSelectPath }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "18px 20px", boxShadow: "var(--shadow-sm)" }}>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, fontWeight: 600, color: "var(--muted)", letterSpacing: "0.06em", textTransform: "uppercase", margin: "0 0 14px" }}>
        Architecture metrics
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 18 }}>
        <MetricPathList title="Top fan-in" items={metrics.top_fan_in} onSelectPath={onSelectPath} formatItem={(item) => item.path} />
        <MetricPathList title="Top fan-out" items={metrics.top_fan_out} onSelectPath={onSelectPath} formatItem={(item) => item.path} />
        <MetricPathList
          title={`Cycles (${metrics.cycle_count})`}
          items={metrics.cycles.flatMap((cycle) => cycle)}
          onSelectPath={onSelectPath}
        />
        <MetricPathList title={`Orphans (${metrics.orphan_count})`} items={metrics.orphans} onSelectPath={onSelectPath} />
      </div>
    </div>
  );
}

function ChartCard({ title, children, minHeight = 260 }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "18px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 14,
        minHeight,
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <p
        style={{
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--muted)",
          margin: 0,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {title}
      </p>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
        {children}
      </div>
    </div>
  );
}

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "graph",    label: "Graph"    },
  { id: "files",    label: "Files"    },
];

const exportButtonStyle = {
  padding: "7px 10px",
  border: "1px solid var(--border)",
  borderRadius: 7,
  background: "var(--surface)",
  color: "var(--fg)",
  cursor: "pointer",
  fontFamily: "'DM Sans', sans-serif",
  fontSize: 12,
  boxShadow: "var(--shadow-md)",
};

export default function DashboardPage({ data, onReset }) {
  const [activeTab, setActiveTab]     = useState("overview");
  const [selectedNode, setSelectedNode] = useState(null);
  const [exportToast, setExportToast] = useState("");
  const [exportToastError, setExportToastError] = useState(false);
  const exportToastTimeout = useRef(null);

  useEffect(() => () => window.clearTimeout(exportToastTimeout.current), []);

  const totalLines = data.nodes.reduce((s, n) => s + (n.line_count || 0), 0);
  const connectedCount = new Set(data.edges.flatMap((e) => [e.source, e.target])).size;
  const selectMetricNode = (path) => {
    const node = data.nodes.find((item) => item.path === path);
    if (!node) return;
    setSelectedNode(node);
    setActiveTab("graph");
  };
  const handleTabKeyDown = (event, currentTab) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = TABS.findIndex((tab) => tab.id === currentTab);
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? TABS.length - 1
        : (currentIndex + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
    const nextTab = TABS[nextIndex].id;
    setActiveTab(nextTab);
    document.getElementById(`dashboard-tab-${nextTab}`)?.focus();
  };
  const exportFilename = `${data.owner}-${data.repo_name}`;
  const notifyExport = async (action, successMessage) => {
    window.clearTimeout(exportToastTimeout.current);
    try {
      await action();
      setExportToast(successMessage);
      setExportToastError(false);
    } catch (error) {
      console.error("Graph export failed:", error);
      setExportToast(error instanceof Error ? error.message : "Export failed.");
      setExportToastError(true);
    }
    exportToastTimeout.current = window.setTimeout(() => setExportToast(""), 3000);
  };

  return (
    <div className="dashboard-root" style={{ height: "100dvh", display: "flex", flexDirection: "column", background: "var(--bg)" }}>

      {/* ── Header ── */}
      <header
        className="dashboard-header"
        style={{
          height: 52,
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 1.25rem",
          background: "var(--surface)",
          flexShrink: 0,
          zIndex: 20,
        }}
      >
        <div className="dashboard-header-brand" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            aria-label="Return to repository search"
            onClick={onReset}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: 0,
              display: "flex",
              alignItems: "center",
              gap: 5,
              color: "var(--muted)",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 13,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            New
          </button>
          <span style={{ color: "var(--border)" }}>|</span>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "var(--muted)" }}>
            {data.owner}/{data.repo_name}
          </span>
          {data.status === "ready" && (
            <span
              style={{
                background: "var(--success-bg)",
                color: "var(--success-fg)",
                fontSize: 11,
                fontFamily: "'DM Sans', sans-serif",
                padding: "2px 7px",
                borderRadius: 6,
              }}
            >
              ready
            </span>
          )}
        </div>

        <div className="dashboard-tabs" role="tablist" aria-label="Repository dashboard" style={{ display: "flex", gap: 2 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`dashboard-tab-${t.id}`}
              type="button"
              role="tab"
              aria-selected={activeTab === t.id}
              tabIndex={activeTab === t.id ? 0 : -1}
              onKeyDown={(event) => handleTabKeyDown(event, t.id)}
              onClick={() => setActiveTab(t.id)}
              style={{
                background: activeTab === t.id ? "var(--bg)" : "transparent",
                color: activeTab === t.id ? "var(--fg)" : "var(--muted)",
                border: "none",
                borderRadius: 7,
                padding: "5px 12px",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 13,
                cursor: "pointer",
                fontWeight: activeTab === t.id ? 500 : 400,
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <a
          href={`https://github.com/${data.owner}/${data.repo_name}`}
          target="_blank"
          rel="noreferrer"
          style={{
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 12,
            color: "var(--muted)",
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          GitHub ↗
        </a>
      </header>

      {(data.discovered_files > data.total_files || data.truncated) && (
        <div
          role="status"
          style={{
            padding: "9px 1.25rem",
            background: "var(--warning-bg)",
            borderBottom: "1px solid var(--warning-border)",
            color: "var(--warning-fg)",
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 12,
            flexShrink: 0,
          }}
        >
          {data.discovered_files > data.total_files && (
            <div>
              Showing {data.total_files.toLocaleString()} of{" "}
              {data.discovered_files.toLocaleString()} files
            </div>
          )}
          {data.truncated && (
            <div>GitHub truncated the repository tree; discovered counts may be incomplete.</div>
          )}
        </div>
      )}

      {/* ── AI Summary ── */}
      {data.summary && (
        <div
          style={{
            borderBottom: "1px solid var(--warning-border)",
            padding: "10px 1.25rem",
            background: "var(--warning-bg)",
            flexShrink: 0,
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "var(--warning-badge)",
              border: "1px solid var(--warning-border)",
              borderRadius: 6,
              padding: "3px 8px",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 11,
              color: "var(--warning-fg)",
              fontWeight: 500,
              flexShrink: 0,
              marginTop: 2,
            }}
          >
            ✦ AI
          </span>
          <p
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 14,
              color: "var(--fg-dim)",
              margin: 0,
              lineHeight: 1.6,
            }}
          >
            {data.summary}
          </p>
        </div>
      )}

      {/* ── Overview ── */}
      {activeTab === "overview" && (
        <div id="dashboard-panel-overview" className="dashboard-overview" role="tabpanel" aria-labelledby="dashboard-tab-overview" tabIndex={0} style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
          {/* Stat row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 10,
              marginBottom: 14,
            }}
          >
            <StatCard
              label="Total files"
              value={data.nodes.length.toLocaleString()}
              icon={ICONS.files}
              tint={{ bg: "var(--card-blue-bg)", fg: "var(--card-blue-fg)" }}
            />
            <StatCard
              label="Connected files"
              value={connectedCount.toLocaleString()}
              sub={data.nodes.length
                ? `${Math.round((connectedCount / data.nodes.length) * 100)}% of codebase`
                : "0% of codebase"}
              icon={ICONS.link}
              tint={{ bg: "var(--card-green-bg)", fg: "var(--card-green-fg)" }}
            />
            <StatCard
              label="Dependencies"
              value={data.edges.length.toLocaleString()}
              sub="import connections"
              icon={ICONS.deps}
              tint={{ bg: "var(--card-red-bg)", fg: "var(--card-red-fg)" }}
            />
            <StatCard
              label="Total lines"
              value={totalLines > 999 ? `${(totalLines / 1000).toFixed(1)}k` : totalLines}
              icon={ICONS.lines}
              tint={{ bg: "var(--card-purple-bg)", fg: "var(--card-purple-fg)" }}
            />
            {data.metrics && (
              <>
                <StatCard
                  label="Cycles"
                  value={data.metrics.cycle_count.toLocaleString()}
                  icon={ICONS.cycles}
                  tint={{ bg: "var(--card-orange-bg)", fg: "var(--card-orange-fg)" }}
                />
                <StatCard
                  label="Orphans"
                  value={data.metrics.orphan_count.toLocaleString()}
                  icon={ICONS.orphans}
                  tint={{ bg: "var(--card-gray-bg)", fg: "var(--card-gray-fg)" }}
                />
              </>
            )}
          </div>

          {/* Chart row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 12,
              marginBottom: 12,
            }}
            className="dashboard-chart-grid"
          >
            <ChartCard title="Languages">
              <LangDonut nodes={data.nodes} />
            </ChartCard>
            <ChartCard title="Complexity">
              <ComplexityChart nodes={data.nodes} />
            </ChartCard>
            <ChartCard title="Connections distribution">
              <ConnectionsChart nodes={data.nodes} edges={data.edges} />
            </ChartCard>
          </div>

          {data.metrics && (
            <div style={{ marginTop: 12 }}>
              <ArchitectureMetrics metrics={data.metrics} onSelectPath={selectMetricNode} />
            </div>
          )}

          {/* Bottom row */}
          <div className="dashboard-bottom-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            <ChartCard title="Most connected files">
              <TopFiles nodes={data.nodes} edges={data.edges} />
            </ChartCard>
            <ChartCard title="File roles">
              <FileRoles nodes={data.nodes} />
            </ChartCard>
          </div>
        </div>
      )}

      {/* ── Graph ── */}
      {activeTab === "graph" && (
        <div id="dashboard-panel-graph" className="dashboard-graph-layout" role="tabpanel" aria-labelledby="dashboard-tab-graph" tabIndex={0} style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
          <GraphView
            nodes={data.nodes}
            edges={data.edges}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
          />
          <div className={`graph-export-actions${selectedNode ? " has-selection" : ""}`} style={{ position: "absolute", zIndex: 5, top: 12, right: selectedNode ? 332 : 12, display: "flex", gap: 6 }}>
            <button type="button" onClick={() => notifyExport(() => exportGraphPng(document.getElementById("dependency-graph-canvas"), exportFilename), "PNG exported.")} style={exportButtonStyle}>PNG</button>
            <button type="button" onClick={() => notifyExport(() => exportGraphJson({ id: data.id, owner: data.owner, name: data.repo_name }, data.nodes, data.edges, exportFilename), "JSON exported.")} style={exportButtonStyle}>JSON</button>
            <button type="button" onClick={() => notifyExport(() => copyMermaidGraph(data.nodes, data.edges), "Mermaid copied to clipboard.")} style={exportButtonStyle}>Copy Mermaid</button>
          </div>
          {exportToast && (
            <p className={`graph-export-toast${selectedNode ? " has-selection" : ""}`} role={exportToastError ? "alert" : "status"} aria-live={exportToastError ? "assertive" : "polite"} style={{ position: "absolute", zIndex: 6, top: 52, right: selectedNode ? 332 : 12, margin: 0, padding: "7px 10px", border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface)", color: "var(--fg)", boxShadow: "var(--shadow-md)", fontFamily: "'DM Sans', sans-serif", fontSize: 12 }}>
              {exportToast}
            </p>
          )}
          <NodeDetail
            key={selectedNode?.id}
            node={selectedNode}
            edges={data.edges}
            repoId={data.id}
            repoOwner={data.owner}
            repoName={data.repo_name}
            repoBranch={data.default_branch}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}

      {/* ── Files ── */}
      {activeTab === "files" && (
        <div id="dashboard-panel-files" className="dashboard-files-layout" role="tabpanel" aria-labelledby="dashboard-tab-files" tabIndex={0} style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <FileListPanel
            nodes={data.nodes}
            edges={data.edges}
            onSelectNode={setSelectedNode}
            selectedNode={selectedNode}
          />
          <NodeDetail
            key={selectedNode?.id}
            node={selectedNode}
            edges={data.edges}
            repoId={data.id}
            repoOwner={data.owner}
            repoName={data.repo_name}
            repoBranch={data.default_branch}
            onClose={() => setSelectedNode(null)}
          />
        </div>
      )}
    </div>
  );
}
