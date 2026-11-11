import { useState } from "react";
import { getLangColor, COMPLEXITY_COLOR } from "../../utils/lang";
import { apiFetch } from "../../utils/api";

function Badge({ children, color = "var(--surface-soft)", textColor = "var(--fg-dim)" }) {
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
          style={{ background: "var(--selected-bg)", borderRadius: 6, padding: "7px 9px" }}
        >
          <p
            style={{
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 10,
              color: "var(--muted)",
              margin: "0 0 2px",
            }}
          >
            {label}
          </p>
          <p
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: 12,
              color: "var(--fg)",
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
  const [showSummaryDetail, setShowSummaryDetail] = useState(false);

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
    if (analysis !== null || (node.ai_summary && node.ai_summary_detail)) return;
    setLoadingAnalysis(true);
    setAnalysisError(null);

    const doFetch = async () => {
      return apiFetch(`/files/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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

  function handleTabKeyDown(event, currentTab) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextTab = event.key === "Home" || (event.key === "ArrowLeft" && currentTab === "content")
      ? "info"
      : event.key === "End" || (event.key === "ArrowRight" && currentTab === "info")
        ? "content"
        : currentTab;
    handleTabChange(nextTab);
    document.getElementById(`file-detail-tab-${nextTab}`)?.focus();
  }

  const effectiveAnalysis = analysis || (node.ai_summary ? {
    ai_summary: node.ai_summary,
    ai_summary_detail: node.ai_summary_detail,
    ai_complexity: node.ai_complexity,
    ai_role: node.ai_role,
  } : null);

  const complexityColor = COMPLEXITY_COLOR[effectiveAnalysis?.ai_complexity?.toLowerCase()] || "var(--muted)";

  return (
    <div
      className="dashboard-detail-panel"
      style={{
        width: 280,
        borderLeft: "1px solid var(--border)",
        background: "var(--surface)",
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
          borderBottom: "1px solid var(--border-soft)",
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
              color: "var(--fg)",
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
                color: "var(--muted)",
                margin: 0,
                wordBreak: "break-all",
              }}
            >
              {dir}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-label={`Close details for ${node.path}`}
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--muted)",
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
        role="tablist"
        aria-label={`${filename} details`}
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border-soft)",
          padding: "0 14px",
          gap: 0,
        }}
      >
        {["info", "content"].map((t) => (
          <button
            key={t}
            id={`file-detail-tab-${t}`}
            type="button"
            role="tab"
            aria-selected={tab === t}
            tabIndex={tab === t ? 0 : -1}
            onClick={() => handleTabChange(t)}
            onKeyDown={(event) => handleTabKeyDown(event, t)}
            style={{
              background: "none",
              border: "none",
              borderBottom: tab === t ? "2px solid var(--fg)" : "2px solid transparent",
              padding: "8px 10px",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              color: tab === t ? "var(--fg)" : "var(--muted)",
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
        <div id="file-detail-panel-info" role="tabpanel" aria-labelledby="file-detail-tab-info" tabIndex={0} style={{ flex: 1, overflowY: "auto" }}>
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-soft)" }}>
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
                role="status"
                aria-live="polite"
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "var(--muted)",
                  margin: 0,
                }}
              >
                Running AI analysis…
              </p>
            )}
            {analysisError && (
              <p
                role="alert"
                style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "var(--status-error)",
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
                      textColor={complexityColor}
                    >
                      {effectiveAnalysis.ai_complexity} complexity
                    </Badge>
                  )}
                </div>
                {effectiveAnalysis.ai_summary && (
                  <div>
                    <p
                      style={{
                        fontFamily: "'DM Sans', sans-serif",
                        fontSize: 12,
                        color: "var(--fg-dim)",
                        lineHeight: 1.65,
                        margin: 0,
                      }}
                    >
                      {effectiveAnalysis.ai_summary}
                    </p>
                    {effectiveAnalysis.ai_summary_detail && (
                      <div style={{ marginTop: 8 }}>
                        <p
                          style={{
                            fontFamily: "'DM Sans', sans-serif",
                            fontSize: 12,
                            color: "var(--fg-dim)",
                            lineHeight: 1.65,
                            margin: 0,
                            display: showSummaryDetail ? "block" : "-webkit-box",
                            WebkitLineClamp: showSummaryDetail ? "none" : 3,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {effectiveAnalysis.ai_summary_detail}
                        </p>
                        <button
                          type="button"
                          onClick={() => setShowSummaryDetail((value) => !value)}
                          style={{
                            marginTop: 6,
                            background: "none",
                            border: "none",
                            color: "var(--status-link)",
                            cursor: "pointer",
                            fontFamily: "'DM Sans', sans-serif",
                            fontSize: 12,
                            padding: 0,
                          }}
                        >
                          {showSummaryDetail ? "Show less" : "Read more"}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {!effectiveAnalysis && !loadingAnalysis && !analysisError && (
              <button
                type="button"
                onClick={fetchAnalysis}
                style={{
                  background: "var(--selected-bg)",
                  border: "1px solid var(--border)",
                  borderRadius: 7,
                  padding: "7px 12px",
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: 12,
                  color: "var(--fg-dim)",
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
        <div id="file-detail-panel-content" role="tabpanel" aria-labelledby="file-detail-tab-content" tabIndex={0} style={{ flex: 1, overflow: "auto", background: "var(--source-bg)" }}>
          {loadingContent ? (
            <div
              role="status"
              aria-live="polite"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "var(--muted)",
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
              }}
            >
              Loading…
            </div>
          ) : (
            <pre
              role={content === "// Could not load file content." ? "alert" : undefined}
              style={{
                margin: 0,
                padding: "12px 14px",
                fontFamily: "'DM Mono', monospace",
                fontSize: 10.5,
                lineHeight: 1.7,
                color: "var(--source-fg)",
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
