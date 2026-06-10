import { useMemo } from "react";

export default function ConnectionsChart({ nodes, edges }) {
  const { bins, maxConn, maxBin } = useMemo(() => {
    const connCount = {};
    nodes.forEach((n) => { connCount[n.path] = 0; });
    edges.forEach((e) => {
      if (connCount[e.source] !== undefined) connCount[e.source]++;
      if (connCount[e.target] !== undefined) connCount[e.target]++;
    });
    const vals = Object.values(connCount);
    const maxConn = Math.max(...vals, 1);
    const bins = new Array(8).fill(0);
    vals.forEach((v) => { bins[Math.min(Math.floor((v / (maxConn + 1)) * 8), 7)]++; });
    return { bins, maxConn, maxBin: Math.max(...bins, 1) };
  }, [nodes, edges]);

  const BAR_H = 90;
  const BAR_W = 22;
  const GAP = 8;
  const CHART_W = bins.length * (BAR_W + GAP) - GAP;
  const LABEL_H = 20;
  const SVG_H = BAR_H + LABEL_H + 8;

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${CHART_W + 8} ${SVG_H}`} style={{ overflow: "visible" }}>
        {bins.map((cnt, i) => {
          const filledH = ((cnt / maxBin) * BAR_H) || 2;
          const y = BAR_H - filledH;
          const x = i * (BAR_W + GAP) + 4;
          const alpha = 0.35 + 0.65 * (i / 7);
          const rangeStart = Math.round((i / 8) * maxConn);
          const rangeEnd = Math.round(((i + 1) / 8) * maxConn);
          const binLabel = `${rangeStart}–${rangeEnd} connections (${cnt} ${cnt === 1 ? "file" : "files"})`;

          return (
            <g key={i}>
              <rect x={x} y={0} width={BAR_W} height={BAR_H} rx={3} fill="#F3F4F6" title={binLabel} />
              <rect
                x={x}
                y={y}
                width={BAR_W}
                height={filledH}
                rx={3}
                fill={`rgba(99,102,241,${alpha})`}
                title={binLabel}
                style={{
                  transition: "height 0.7s cubic-bezier(.4,0,.2,1), y 0.7s cubic-bezier(.4,0,.2,1)",
                }}
              />
            </g>
          );
        })}
        <text x={4} y={SVG_H - 2} style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, fill: "#9CA3AF" }}>0</text>
        <text x={CHART_W + 4} y={SVG_H - 2} textAnchor="end" style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, fill: "#9CA3AF" }}>{maxConn}</text>
      </svg>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#9CA3AF", marginTop: 4, textAlign: "center" }}>
        connections per file (0 → max)
      </p>
    </div>
  );
}
