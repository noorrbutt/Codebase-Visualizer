import { useMemo } from "react";

const ROLE_COLOR = {
  entry_point: "var(--role-entry)",
  api_router: "var(--role-api)",
  data_model: "var(--role-model)",
  service: "var(--role-service)",
  utility: "var(--role-utility)",
  config: "var(--accent-pink)",
  test: "var(--role-test)",
  static: "var(--role-static)",
  unknown: "var(--complexity-unknown)",
};

export default function FileRoles({ nodes }) {
  const entries = useMemo(() => {
    const roles = {};
    nodes.forEach((n) => {
      const role = n.ai_role ?? n.role;
      if (!role) return;
      roles[role] = (roles[role] || 0) + 1;
    });
    return Object.entries(roles).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [nodes]);

  if (!entries.length) {
    return (
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)", margin: 0 }}>
        Automatic file analysis is pending or unavailable
      </p>
    );
  }

  const max = entries[0][1];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {entries.map(([role, count]) => {
        const pct = (count / max) * 100;
        const color = ROLE_COLOR[role] || "var(--role-entry)";
        return (
          <div key={role} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
                color: "var(--fg-dim)",
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
                background: "var(--surface-soft)",
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
                color: "var(--muted)",
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
