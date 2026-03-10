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
      <div className="flex h-[200px] items-center justify-center text-sm text-gray-400">
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
            stroke="white"
            strokeWidth={2}
          />
        ))}
        {/* Center label */}
        <text
          x={cx}
          y={cy - 8}
          textAnchor="middle"
          fontSize={11}
          fill="#6b7280"
        >
          Total raised
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          fontSize={16}
          fontWeight={600}
          fill="#111827"
        >
          {formatDollars(total)}
        </text>
      </svg>

      {/* Legend */}
      <ul className="mt-3 space-y-1.5">
        {data.slice(0, 6).map((d) => (
          <li key={d.industry} className="flex items-center gap-2 text-xs text-gray-600">
            <span
              className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-sm"
              style={{ background: colorFor(d.industry) }}
            />
            <span className="flex-1 truncate">
              {INDUSTRY_LABEL[d.industry] ?? d.industry}
            </span>
            <span className="font-medium text-gray-800">
              {formatDollars(d.total_cents)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
