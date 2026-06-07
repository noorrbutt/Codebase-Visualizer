import { useMemo } from "react";
import { getLangColor } from "../../utils/lang";

export default function TopFiles({ nodes, edges }) {
  const ranked = useMemo(() => {
    const connCount = {};
    nodes.forEach((n) => { connCount[n.path] = 0; });
    edges.forEach((e) => {
      if (connCount[e.source] !== undefined) connCount[e.source]++;
      if (connCount[e.target] !== undefined) connCount[e.target]++;
    });
    return [...nodes]
      .sort((a, b) => (connCount[b.path] || 0) - (connCount[a.path] || 0))
      .slice(0, 8)
      .map((n) => ({ ...n, connections: connCount[n.path] || 0 }));
  }, [nodes, edges]);

  const maxConn = ranked[0]?.connections || 1;

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      {ranked.map((n, i) => {
        const pct = (n.connections / maxConn) * 100;
        const filename = n.path.split("/").pop();
        return (
          <div
            key={n.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 0",
              borderBottom: i < ranked.length - 1 ? "1px solid #F3F4F6" : "none",
            }}
          >
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 10,
                color: "#D1D5DB",
                width: 14,
                textAlign: "right",
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: getLangColor(n.language),
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 11,
                color: "#374151",
                flex: 1,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={n.path}
            >
              {filename}
            </span>
            <div
              style={{
                width: 80,
                height: 4,
                background: "#F3F4F6",
                borderRadius: 2,
                flexShrink: 0,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: getLangColor(n.language),
                  borderRadius: 2,
                  transition: "width 0.6s cubic-bezier(.4,0,.2,1)",
                }}
              />
            </div>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 10,
                color: "#9CA3AF",
                width: 20,
                textAlign: "right",
                flexShrink: 0,
              }}
            >
              {n.connections}
            </span>
          </div>
        );
      })}
    </div>
  );
}
