import { useMemo } from "react";

const BARS = [
  { key: "low",     label: "Low",  color: "var(--accent-green)" },
  { key: "medium",  label: "Med",  color: "var(--accent-amber)" },
  { key: "high",    label: "High", color: "var(--accent-red)" },
  { key: "unknown", label: "N/A",  color: "var(--complexity-unknown)" },
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

  const total = Object.values(counts).reduce((s, v) => s + v, 0);
  const analyzed = counts.low + counts.medium + counts.high;

  const SIZE = 130;
  const CX = SIZE / 2;
  const CY = SIZE / 2;
  const R = 50;
  const INNER = 33;
  const STROKE = R - INNER;
  const CIRCUMFERENCE = 2 * Math.PI * (R - STROKE / 2);

  const slices = useMemo(() => {
    // build slices and compute cumulative offsets without reassigning a variable
    const result = BARS.filter((b) => counts[b.key] > 0).reduce(
      (acc, b) => {
        const pct = counts[b.key] / total;
        const dash = pct * CIRCUMFERENCE;
        acc.slices.push({ ...b, count: counts[b.key], pct, dash, offset: acc.totalOffset });
        acc.totalOffset += dash;
        return acc;
      },
      { slices: [], totalOffset: 0 }
    );

    return result.slices;
  }, [counts, total, CIRCUMFERENCE]);

  if (total === 0 || analyzed === 0) {
    return (
      <div
        style={{
          height: SIZE,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: "var(--muted)" }}>
          Automatic file analysis is pending or unavailable
        </span>
        <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 11, color: "var(--muted)" }}>
          Results appear once AI analysis finishes
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
      <svg width={SIZE} height={SIZE} style={{ flexShrink: 0, overflow: "visible" }}>
        {slices.map(({ key, dash, offset, color }, i) => (
          <circle
            key={key}
            cx={CX}
            cy={CY}
            r={R - STROKE / 2}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
            strokeDashoffset={-offset + CIRCUMFERENCE / 4}
            style={{
              transition: "stroke-dasharray 0.6s cubic-bezier(.4,0,.2,1)",
              animationDelay: `${i * 80}ms`,
            }}
          />
        ))}
        <text
          x={CX}
          y={CY - 5}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{ fontFamily: "'DM Mono', monospace", fontSize: 18, fontWeight: 600, fill: "var(--fg)" }}
        >
          {total}
        </text>
        <text
          x={CX}
          y={CY + 12}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, fill: "var(--muted)" }}
        >
          files
        </text>
      </svg>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        {BARS.map(({ key, label, color }) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: 3,
                background: color,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
                color: "var(--fg-dim)",
                flex: 1,
              }}
            >
              {label}
            </span>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 12,
                fontWeight: 600,
                color: "var(--fg)",
                minWidth: 20,
                textAlign: "right",
              }}
            >
              {counts[key]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
