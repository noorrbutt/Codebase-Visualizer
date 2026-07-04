import { useMemo } from "react";

export default function ConnectionsChart({ nodes, edges }) {
  const { points, maxConn, maxBin } = useMemo(() => {
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
    return { points: bins, maxConn, maxBin: Math.max(...bins, 1) };
  }, [nodes, edges]);

  const W = 480;
  const H = 130;
  const PAD_L = 22;
  const PAD_R = 8;
  const PAD_T = 14;
  const PAD_B = 22;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const GRID_LINES = 4;
  const stepX = plotW / (points.length - 1);

  const coords = points.map((v, i) => ({
    x: PAD_L + i * stepX,
    y: PAD_T + plotH - (v / maxBin) * plotH,
    v,
  }));

  const linePath = coords.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${PAD_T + plotH} L ${coords[0].x} ${PAD_T + plotH} Z`;

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: "visible" }}>
        <defs>
          <linearGradient id="connFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366F1" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#6366F1" stopOpacity="0" />
          </linearGradient>
        </defs>

        {Array.from({ length: GRID_LINES + 1 }).map((_, i) => {
          const gy = PAD_T + (plotH / GRID_LINES) * i;
          const val = Math.round(maxBin - (maxBin / GRID_LINES) * i);
          return (
            <g key={i}>
              <line x1={PAD_L} x2={W - PAD_R} y1={gy} y2={gy} stroke="#F0F1F3" strokeWidth={1} />
              <text x={PAD_L - 6} y={gy + 3} textAnchor="end" style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, fill: "#B3B7BE" }}>
                {val}
              </text>
            </g>
          );
        })}

        <path d={areaPath} fill="url(#connFill)" />
        <path d={linePath} fill="none" stroke="#6366F1" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

        {coords.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill="#fff" stroke="#6366F1" strokeWidth={2} />
        ))}

        {coords.map((p, i) => {
          const rangeStart = Math.round((i / 8) * maxConn);
          const rangeEnd = Math.round(((i + 1) / 8) * maxConn);
          return (
            <text
              key={i}
              x={p.x}
              y={H - 4}
              textAnchor="middle"
              style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, fill: "#9CA3AF" }}
            >
              {rangeStart}-{rangeEnd}
            </text>
          );
        })}
      </svg>
      <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 10, color: "#9CA3AF", marginTop: 6, textAlign: "center" }}>
        files per connection-count range
      </p>
    </div>
  );
}
