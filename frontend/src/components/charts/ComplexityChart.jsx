import { useMemo } from "react";

const BARS = [
  { key: "low",     label: "Low",  color: "#10B981" },
  { key: "medium",  label: "Med",  color: "#F59E0B" },
  { key: "high",    label: "High", color: "#EF4444" },
  { key: "unknown", label: "N/A",  color: "#E5E7EB" },
];

export default function ComplexityChart({ nodes }) {
  const counts = useMemo(() => {
    const c = { low: 0, medium: 0, high: 0, unknown: 0 };
    nodes.forEach((n) => {
      const k = n.ai_complexity?.toLowerCase();
      if (k === "low" || k === "medium" || k === "high") c[k]++;
      else c.unknown++;
    });
    return c;
  }, [nodes]);

  const max = Math.max(...BARS.map((b) => counts[b.key]), 1);
  const BAR_H = 120;
  const BAR_W = 36;
  const GAP = 16;
  const CHART_W = BARS.length * (BAR_W + GAP) - GAP;
  const LABEL_H = 24;
  const SVG_H = BAR_H + LABEL_H + 16;

  return (
    <svg width="100%" viewBox={`0 0 ${CHART_W + 8} ${SVG_H}`} style={{ overflow: "visible" }}>
      {BARS.map(({ key, label, color }, i) => {
        const count = counts[key];
        const filledH = ((count / max) * BAR_H) || 2;
        const y = BAR_H - filledH;
        const x = i * (BAR_W + GAP) + 4;

        return (
          <g key={key}>
            {/* track */}
            <rect
              x={x}
              y={0}
              width={BAR_W}
              height={BAR_H}
              rx={4}
              fill="#F3F4F6"
            />
            {/* fill */}
            <rect
              x={x}
              y={y}
              width={BAR_W}
              height={filledH}
              rx={4}
              fill={color}
              style={{
                transition: "height 0.7s cubic-bezier(.4,0,.2,1), y 0.7s cubic-bezier(.4,0,.2,1)",
              }}
            />
            {/* count label */}
            {count > 0 && (
              <text
                x={x + BAR_W / 2}
                y={y - 5}
                textAnchor="middle"
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 11,
                  fill: "#374151",
                  fontWeight: 600,
                }}
              >
                {count}
              </text>
            )}
            {/* x label */}
            <text
              x={x + BAR_W / 2}
              y={BAR_H + 16}
              textAnchor="middle"
              style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, fill: "#9CA3AF" }}
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
