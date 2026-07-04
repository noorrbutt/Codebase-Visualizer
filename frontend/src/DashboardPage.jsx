import { useState } from "react";
import LangDonut from "./components/charts/LangDonut";
import ComplexityChart from "./components/charts/ComplexityChart";
import ConnectionsChart from "./components/charts/ConnectionsChart";
import TopFiles from "./components/charts/TopFiles";
import FileRoles from "./components/charts/FileRoles";
import GraphView from "./components/graph/GraphView";
import FileListPanel from "./components/panels/FileListPanel";
import NodeDetail from "./components/panels/NodeDetail";

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
        boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
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
              color: "var(--subtle)",
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
};

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
        boxShadow: "0 1px 2px rgba(16,24,40,0.04)",
      }}
    >
      <p
        style={{
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 11,
          fontWeight: 600,
          color: "var(--subtle)",
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

export default function DashboardPage({ data, onReset }) {
  const [activeTab, setActiveTab]     = useState("overview");
  const [selectedNode, setSelectedNode] = useState(null);

  const totalLines = data.nodes.reduce((s, n) => s + (n.line_count || 0), 0);
  const connectedCount = new Set(data.edges.flatMap((e) => [e.source, e.target])).size;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--bg)" }}>

      {/* ── Header ── */}
      <header
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
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
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
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: "var(--subtle)" }}>
            {data.owner}/{data.repo_name}
          </span>
          {data.status === "ready" && (
            <span
              style={{
                background: "#F0FDF4",
                color: "#166534",
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

        <div style={{ display: "flex", gap: 2 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
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

      {/* ── AI Summary ── */}
      {data.summary && (
        <div
          style={{
            borderBottom: "1px solid #FEF3C7",
            padding: "10px 1.25rem",
            background: "#FFFBEB",
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
              background: "#FEF9C3",
              border: "1px solid #FDE68A",
              borderRadius: 6,
              padding: "3px 8px",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 11,
              color: "#92400E",
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
              color: "#1F2937",
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
        <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
          {/* Stat row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 10,
              marginBottom: 14,
            }}
          >
            <StatCard
              label="Total files"
              value={data.nodes.length.toLocaleString()}
              icon={ICONS.files}
              tint={{ bg: "#EEF2FF", fg: "#4F46E5" }}
            />
            <StatCard
              label="Connected files"
              value={connectedCount.toLocaleString()}
              sub={`${Math.round((connectedCount / data.nodes.length) * 100)}% of codebase`}
              icon={ICONS.link}
              tint={{ bg: "#ECFDF5", fg: "#059669" }}
            />
            <StatCard
              label="Dependencies"
              value={data.edges.length.toLocaleString()}
              sub="import connections"
              icon={ICONS.deps}
              tint={{ bg: "#FEF2F2", fg: "#DC2626" }}
            />
            <StatCard
              label="Total lines"
              value={totalLines > 999 ? `${(totalLines / 1000).toFixed(1)}k` : totalLines}
              icon={ICONS.lines}
              tint={{ bg: "#F5F3FF", fg: "#7C3AED" }}
            />
          </div>

          {/* Chart row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 12,
              marginBottom: 12,
            }}
          >
            <ChartCard title="Languages">
              <LangDonut nodes={data.nodes} />
            </ChartCard>
            <ChartCard title="Complexity">
              <ComplexityChart nodes={data.nodes} repoId={data.id} />
            </ChartCard>
            <ChartCard title="Connections distribution">
              <ConnectionsChart nodes={data.nodes} edges={data.edges} />
            </ChartCard>
          </div>

          {/* Bottom row */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <ChartCard title="Most connected files">
              <TopFiles nodes={data.nodes} edges={data.edges} />
            </ChartCard>
            <ChartCard title="File roles">
              <FileRoles nodes={data.nodes} repoId={data.id} />
            </ChartCard>
          </div>
        </div>
      )}

      {/* ── Graph ── */}
      {activeTab === "graph" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <GraphView
            nodes={data.nodes}
            edges={data.edges}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
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

      {/* ── Files ── */}
      {activeTab === "files" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
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
