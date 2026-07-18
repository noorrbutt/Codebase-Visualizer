import { useEffect, useMemo, useState } from "react";
import { API } from "../../utils/lang";

const ROLE_COLOR = {
  entry_point: "#6366F1",
  api_router: "#3B82F6",
  data_model: "#10B981",
  service: "#F59E0B",
  utility: "#8B5CF6",
  config: "#EC4899",
  test: "#9CA3AF",
  static: "#D1D5DB",
  unknown: "#E5E7EB",
};

export default function FileRoles({ nodes, repoId }) {
  const [polledNodes, setPolledNodes] = useState(nodes);

  const displayNodes = useMemo(() => {
    const hasUnanalyzed = nodes.some((n) => n.ai_role === null);
    return hasUnanalyzed ? polledNodes : nodes;
  }, [nodes, polledNodes]);

  useEffect(() => {
    if (!repoId) return;

    const hasUnanalyzed = nodes.some((n) => n.ai_role === null);
    if (!hasUnanalyzed) return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API}/repos/${repoId}`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.status === "ready") {
          setPolledNodes(data.nodes);
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Failed to poll repo status:", err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [repoId, nodes]);

  const entries = useMemo(() => {
    const roles = {};
    displayNodes.forEach((n) => {
      if (!n.ai_role) return;
      roles[n.ai_role] = (roles[n.ai_role] || 0) + 1;
    });
    return Object.entries(roles).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [displayNodes]);

  if (!entries.length) {
    return (
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "#9CA3AF", margin: 0 }}>
      Click a file and run "Analyze" to populate this chart
      </p>
    );
  }

  const max = entries[0][1];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {entries.map(([role, count]) => {
        const pct = (count / max) * 100;
        const color = ROLE_COLOR[role] || "#6366F1";
        return (
          <div key={role} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
                color: "#4B5563",
                textTransform: "capitalize",
                width: 110,
                flexShrink: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {role.replace(/_/g, " ")}
            </span>
            <div
              style={{
                flex: 1,
                height: 6,
                background: "#F3F4F6",
                borderRadius: 3,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: color,
                  borderRadius: 3,
                  transition: "width 0.7s cubic-bezier(.4,0,.2,1)",
                }}
              />
            </div>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 10,
                color: "#9CA3AF",
                width: 22,
                textAlign: "right",
                flexShrink: 0,
              }}
            >
              {count}
            </span>
          </div>
        );
      })}
    </div>
  );
}
