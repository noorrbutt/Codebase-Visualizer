import { useState } from "react";
import LangDonut from "./components/charts/LangDonut";
import ComplexityChart from "./components/charts/ComplexityChart";
import ConnectionsChart from "./components/charts/ConnectionsChart";
import TopFiles from "./components/charts/TopFiles";
import FileRoles from "./components/charts/FileRoles";
import GraphView from "./components/graph/GraphView";
import FileListPanel from "./components/panels/FileListPanel";
import NodeDetail from "./components/panels/NodeDetail";

function StatCard({ label, value, sub }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        gap: 3,
      }}
    >
      <span
        style={{
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 11,
          color: "var(--subtle)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "'Instrument Serif', Georgia, serif",
          fontSize: 30,
          color: "var(--fg)",
          lineHeight: 1.1,
        }}
      >
        {value}
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
  );
}

function ChartCard({ title, children }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <p
        style={{
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 11,
          color: "var(--subtle)",
          margin: 0,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
        }}
      >
        {title}
      </p>
      {children}
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
            <StatCard label="Total files" value={data.nodes.length.toLocaleString()} />
            <StatCard
              label="Connected files"
              value={connectedCount.toLocaleString()}
              sub={`${Math.round((connectedCount / data.nodes.length) * 100)}% of codebase`}
            />
            <StatCard
              label="Dependencies"
              value={data.edges.length.toLocaleString()}
              sub="import connections"
            />
            <StatCard
              label="Total lines"
              value={totalLines > 999 ? `${(totalLines / 1000).toFixed(1)}k` : totalLines}
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
