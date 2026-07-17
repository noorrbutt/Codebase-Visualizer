import { useState } from "react";
import { getLangColor, COMPLEXITY_COLOR, API } from "../../utils/lang";

function Badge({ children, color = "#F3F4F6", textColor = "#374151" }) {
  return (
    <span
      style={{
        display: "inline-block",
        background: color,
        color: textColor,
        borderRadius: 5,
        padding: "2px 8px",
        fontFamily: "'DM Sans', sans-serif",
        fontSize: 11,
        textTransform: "capitalize",
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  );
}

function MetaGrid({ items }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
      {items.map(({ label, value }) => (
        <div
          key={label}
          style={{ background: "#F9FAFB", borderRadius: 6, padding: "7px 9px" }}
        >
          <p
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 10,
              color: "#9CA3AF",
              margin: "0 0 2px",
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 12,
              color: "#111",
              margin: 0,
              textTransform: "capitalize",
            }}
          >
            {value ?? "—"}
          </p>
        </div>
      ))}
    </div>
  );
}

export default function NodeDetail({ node, edges, repoId, repoOwner, repoName, repoBranch, onClose }) {
  const [tab, setTab] = useState("info");
  const [content, setContent] = useState(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  if (!node) return null;

  const inbound = edges.filter((e) => e.target === node.id || e.target === node.path).length;
  const outbound = edges.filter((e) => e.source === node.id || e.source === node.path).length;
  const filename = node.path.split("/").pop();
  const dir = node.path.includes("/") ? node.path.substring(0, node.path.lastIndexOf("/")) : "";

  async function fetchContent() {
    if (content !== null) return;
    setLoadingContent(true);
    try {
      const url = `https://raw.githubusercontent.com/${repoOwner}/${repoName}/${repoBranch}/${node.path}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Not found");
      setContent(await res.text());
    } catch {
      setContent("// Could not load file content.");
    } finally {
      setLoadingContent(false);
    }
  }

  async function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function fetchAnalysis() {
    if (analysis !== null || node.ai_summary) return;
    setLoadingAnalysis(true);
    setAnalysisError(null);

    const doFetch = async () => {
      return fetch(`${API}/files/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": import.meta.env.VITE_API_KEY,

        },
        body: JSON.stringify({ repo_id: repoId, file_path: node.path }),
      });
    };

    try {
      let res = await doFetch();
      if (res.status === 503) {
        await delay(4000);
        res = await doFetch();
      }

      if (!res.ok) {
        throw new Error("Analysis failed");
      }

      const data = await res.json();
      setAnalysis(data);
    } catch {
      setAnalysisError("Analysis failed — try again later.");
    } finally {
      setLoadingAnalysis(false);
    }
  }

  function handleTabChange(t) {
    setTab(t);
    if (t === "content") fetchContent();
    if (t === "info") fetchAnalysis();
  }

  const effectiveAnalysis = analysis || (node.ai_summary ? {
    ai_summary: node.ai_summary,
    ai_complexity: node.ai_complexity,
    ai_role: node.ai_role,
  } : null);

  const complexityColor = COMPLEXITY_COLOR[effectiveAnalysis?.ai_complexity?.toLowerCase()] || "#9CA3AF";

  return (
    <div
      style={{
        width: 280,
        borderLeft: "1px solid #E5E7EB",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid #F3F4F6",
          display: "flex",
          alignItems: "flex-start",
          gap: 8,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: getLangColor(node.language),
            marginTop: 4,
            flexShrink: 0,
          }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 12,
              color: "#111",
              margin: "0 0 2px",
              wordBreak: "break-all",
              fontWeight: 500,
            }}
          >
            {filename}
          </p>
          {dir && (
            <p
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 10,
                color: "#9CA3AF",
                margin: 0,
                wordBreak: "break-all",
              }}
            >
              {dir}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#9CA3AF",
            fontSize: 18,
            lineHeight: 1,
            padding: 2,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid #F3F4F6",
          padding: "0 14px",
          gap: 0,
        }}
      >
        {["info", "content"].map((t) => (
          <button
            key={t}
            onClick={() => handleTabChange(t)}
            style={{
              background: "none",
              border: "none",
              borderBottom: tab === t ? "2px solid #111" : "2px solid transparent",
              padding: "8px 10px",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              color: tab === t ? "#111" : "#9CA3AF",
              cursor: "pointer",
              fontWeight: tab === t ? 500 : 400,
              textTransform: "capitalize",
              marginBottom: -1,
            }}
          >
            {t === "info" ? "Info" : "Source"}
          </button>
        ))}
      </div>

      {/* Tab: Info */}
      {tab === "info" && (
        <div style={{ flex: 1, overflowY: "auto" }}>
          <div style={{ padding: "12px 14px", borderBottom: "1px solid #F3F4F6" }}>
            <MetaGrid
              items={[
                { label: "Language", value: node.language },
                { label: "Lines", value: node.line_count?.toLocaleString() || "0" },
                { label: "Imports", value: node.import_count },
                { label: "Inbound", value: inbound },
                { label: "Outbound", value: outbound },
              ]}
            />
          </div>

          {/* AI Analysis */}
          <div style={{ padding: "12px 14px" }}>
            {loadingAnalysis && (
              <p
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "#9CA3AF",
                  margin: 0,
                }}
              >
                Running AI analysis…
              </p>
            )}
            {analysisError && (
              <p
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "#EF4444",
                  margin: 0,
                }}
              >
                {analysisError}
              </p>
            )}
            {effectiveAnalysis && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {effectiveAnalysis.ai_role && (
                    <Badge>{effectiveAnalysis.ai_role.replace(/_/g, " ")}</Badge>
                  )}
                  {effectiveAnalysis.ai_complexity && (
                    <Badge
                      color={`${complexityColor}22`}
                      textColor={complexityColor}
                    >
                      {effectiveAnalysis.ai_complexity} complexity
                    </Badge>
                  )}
                </div>
                {effectiveAnalysis.ai_summary && (
                  <p
                    style={{
                      fontFamily: "'DM Sans', sans-serif",
                      fontSize: 12,
                      color: "#4B5563",
                      lineHeight: 1.65,
                      margin: 0,
                    }}
                  >
                    {effectiveAnalysis.ai_summary}
                  </p>
                )}
              </div>
            )}
            {!effectiveAnalysis && !loadingAnalysis && !analysisError && (
              <button
                onClick={fetchAnalysis}
                style={{
                  background: "#F9FAFB",
                  border: "1px solid #E5E7EB",
                  borderRadius: 7,
                  padding: "7px 12px",
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "#374151",
                  cursor: "pointer",
                  width: "100%",
                  textAlign: "left",
                }}
              >
                ✦ Run AI analysis
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tab: Source */}
      {tab === "content" && (
        <div style={{ flex: 1, overflow: "auto", background: "#FAFAF9" }}>
          {loadingContent ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "#9CA3AF",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
              }}
            >
              Loading…
            </div>
          ) : (
            <pre
              style={{
                margin: 0,
                padding: "12px 14px",
                fontFamily: "'DM Mono', monospace",
                fontSize: 10.5,
                lineHeight: 1.7,
                color: "#1F2937",
                whiteSpace: "pre",
                overflowX: "auto",
              }}
            >
              {content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
