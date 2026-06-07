import { useMemo } from "react";
import { getLangColor } from "../../utils/lang";

export default function LangDonut({ nodes }) {
  const entries = useMemo(() => {
    const counts = {};
    nodes.forEach((n) => {
      const lang = n.language || "unknown";
      counts[lang] = (counts[lang] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [nodes]);

  const total = entries.reduce((s, [, c]) => s + c, 0);

  const SIZE = 120;
  const CX = SIZE / 2;
  const CY = SIZE / 2;
  const R = 46;
  const INNER = 30;
  const STROKE = R - INNER;
  const CIRCUMFERENCE = 2 * Math.PI * (R - STROKE / 2);

  let offset = 0;
  const slices = entries.map(([lang, count]) => {
    const pct = count / total;
    const dash = pct * CIRCUMFERENCE;
    const slice = { lang, count, pct, dash, offset };
    offset += dash;
    return slice;
  });

  return (
    <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
      <svg width={SIZE} height={SIZE} style={{ flexShrink: 0, overflow: "visible" }}>
        {slices.map(({ lang, dash, offset: off }, i) => (
          <circle
            key={lang}
            cx={CX}
            cy={CY}
            r={R - STROKE / 2}
            fill="none"
            stroke={getLangColor(lang)}
            strokeWidth={STROKE}
            strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
            strokeDashoffset={-off + CIRCUMFERENCE / 4}
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
          style={{ fontFamily: "'DM Mono', monospace", fontSize: 16, fontWeight: 600, fill: "#111" }}
        >
          {total}
        </text>
        <text
          x={CX}
          y={CY + 10}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, fill: "#9CA3AF" }}
        >
          files
        </text>
      </svg>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {entries.map(([lang, count]) => (
          <div key={lang} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: getLangColor(lang),
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: "'DM Sans', sans-serif",
                fontSize: 12,
                color: "#374151",
                flex: 1,
                textTransform: "capitalize",
              }}
            >
              {lang}
            </span>
            <span
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 11,
                color: "#9CA3AF",
                minWidth: 30,
                textAlign: "right",
              }}
            >
              {((count / total) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
