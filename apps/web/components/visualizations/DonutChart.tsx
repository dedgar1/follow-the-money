/**
 * Donut chart — pure React SVG, server-renderable, no D3 required.
 * D3 is reserved for the Sprint 6 network graph.
 */

import type { IndustrySummary } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

const INDUSTRY_LABEL: Record<string, string> = {
  finance: "Finance",
  energy: "Energy",
  health: "Health",
  technology: "Technology",
  agriculture: "Agriculture",
  defense: "Defense",
  real_estate: "Real Estate",
  telecom: "Telecom",
  transportation: "Transportation",
  labor: "Labor",
  education: "Education",
  other: "Other",
};

const INDUSTRY_COLOR: Record<string, string> = {
  finance: "#3b82f6",
  energy: "#f59e0b",
  health: "#10b981",
  technology: "#8b5cf6",
  agriculture: "#84cc16",
  defense: "#6b7280",
  real_estate: "#f97316",
  telecom: "#06b6d4",
  transportation: "#ec4899",
  labor: "#14b8a6",
  education: "#a78bfa",
  other: "#94a3b8",
};

function colorFor(industry: string): string {
  return INDUSTRY_COLOR[industry.toLowerCase()] ?? "#94a3b8";
}

function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startDeg: number,
  endDeg: number,
): string {
  // Clamp to avoid degenerate paths at exactly 360°
  const clampedEnd = Math.min(endDeg, startDeg + 359.99);
  const o1 = polarToXY(cx, cy, outerR, startDeg);
  const o2 = polarToXY(cx, cy, outerR, clampedEnd);
  const i1 = polarToXY(cx, cy, innerR, clampedEnd);
  const i2 = polarToXY(cx, cy, innerR, startDeg);
  const large = clampedEnd - startDeg > 180 ? 1 : 0;
  return [
    `M ${o1.x.toFixed(2)} ${o1.y.toFixed(2)}`,
    `A ${outerR} ${outerR} 0 ${large} 1 ${o2.x.toFixed(2)} ${o2.y.toFixed(2)}`,
    `L ${i1.x.toFixed(2)} ${i1.y.toFixed(2)}`,
    `A ${innerR} ${innerR} 0 ${large} 0 ${i2.x.toFixed(2)} ${i2.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

interface Props {
  data: IndustrySummary[];
  size?: number;
}

export function DonutChart({ data, size = 280 }: Props) {
  if (!data.length) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "#444" }}>
        No funding data available
      </div>
    );
  }

  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 12;
  const innerR = outerR * 0.55;
  const total = data.reduce((s, d) => s + d.total_cents, 0);

  // Build arc slices
  const slices: { path: string; color: string; item: IndustrySummary }[] = [];
  let cursor = 0;
  for (const item of data) {
    const sweep = (item.total_cents / total) * 360;
    slices.push({
      path: arcPath(cx, cy, outerR, innerR, cursor, cursor + sweep),
      color: colorFor(item.industry),
      item,
    });
    cursor += sweep;
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        className="w-full max-w-[280px]"
        aria-label="Top industries donut chart"
      >
        {slices.map(({ path, color, item }) => (
          <path
            key={item.industry}
            d={path}
            fill={color}
            stroke="var(--black)"
            strokeWidth={2}
          />
        ))}
        {/* Center label */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fontSize={11}
          fill="#555"
        >
          Total raised
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          fontSize={16}
          fontWeight={600}
          fill="var(--yellow)"
        >
          {formatDollars(total)}
        </text>
      </svg>

      {/* Legend */}
      <ul style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6, listStyle: "none" }}>
        {data.slice(0, 6).map((d) => (
          <li key={d.industry} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11 }}>
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                flexShrink: 0,
                borderRadius: 2,
                background: colorFor(d.industry),
              }}
            />
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#888", textTransform: "capitalize" }}>
              {INDUSTRY_LABEL[d.industry] ?? d.industry}
            </span>
            <span style={{ fontWeight: 600, color: "var(--white)" }}>
              {formatDollars(d.total_cents)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
