/**
 * Treemap — pure React SVG, server-renderable.
 * Uses a simple row-based squarified layout.
 */

import type { IndustrySummary } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

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
  energy_natural_resources: "#f59e0b",
  finance_insurance: "#3b82f6",
  health_education: "#10b981",
};

function colorFor(industry: string): string {
  const key = industry.toLowerCase();
  return INDUSTRY_COLOR[key] ?? "#94a3b8";
}

interface Rect {
  x: number; y: number; w: number; h: number;
  item: IndustrySummary;
}

/** Simple sliced treemap layout — splits by largest value first */
function layout(
  items: IndustrySummary[],
  x: number,
  y: number,
  w: number,
  h: number,
  total: number,
): Rect[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [{ x, y, w, h, item: items[0] }];
  }

  // Split list into two halves by value sum
  let half = 0;
  let running = 0;
  for (let i = 0; i < items.length; i++) {
    running += items[i].total_cents;
    if (running >= total / 2) { half = i + 1; break; }
  }
  half = Math.max(1, Math.min(half, items.length - 1));

  const firstHalf = items.slice(0, half);
  const secondHalf = items.slice(half);
  const firstSum = firstHalf.reduce((s, d) => s + d.total_cents, 0);
  const ratio = firstSum / total;

  let r1: Rect[], r2: Rect[];
  if (w >= h) {
    // Split horizontally
    const w1 = w * ratio;
    r1 = layout(firstHalf, x, y, w1, h, firstSum);
    r2 = layout(secondHalf, x + w1, y, w - w1, h, total - firstSum);
  } else {
    // Split vertically
    const h1 = h * ratio;
    r1 = layout(firstHalf, x, y, w, h1, firstSum);
    r2 = layout(secondHalf, x, y + h1, w, h - h1, total - firstSum);
  }
  return [...r1, ...r2];
}

interface Props {
  data: IndustrySummary[];
  total: number;
  width?: number;
  height?: number;
}

export function Treemap({ data, total, width = 560, height = 320 }: Props) {
  if (!data.length) {
    return (
      <div
        style={{
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          color: "#444",
        }}
      >
        No funding data available
      </div>
    );
  }

  const sorted = [...data].sort((a, b) => b.total_cents - a.total_cents);
  const dataTotal = total > 0 ? total : sorted.reduce((s, d) => s + d.total_cents, 0);
  const rects = layout(sorted, 2, 2, width - 4, height - 4, dataTotal);
  const PAD = 2;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className="w-full"
      aria-label="Industry funding treemap"
    >
      {rects.map(({ x, y, w, h, item }) => {
        const color = colorFor(item.industry);
        const label = item.industry.replace(/_/g, " ");
        const showText = w > 60 && h > 28;
        return (
          <g key={item.industry}>
            <rect
              x={x + PAD}
              y={y + PAD}
              width={Math.max(0, w - PAD * 2)}
              height={Math.max(0, h - PAD * 2)}
              rx={3}
              fill={color}
              fillOpacity={0.85}
              stroke="var(--black)"
              strokeWidth={1}
            />
            {showText && (
              <>
                <text
                  x={x + PAD + 8}
                  y={y + PAD + 16}
                  fontSize={Math.min(11, w / 8)}
                  fill="rgba(255,255,255,0.9)"
                  fontWeight={600}
                  style={{ pointerEvents: "none" }}
                >
                  {label.length > 16 ? `${label.slice(0, 14)}…` : label}
                </text>
                {h > 44 && (
                  <text
                    x={x + PAD + 8}
                    y={y + PAD + 30}
                    fontSize={Math.min(10, w / 9)}
                    fill="rgba(255,255,255,0.6)"
                    style={{ pointerEvents: "none" }}
                  >
                    {formatDollars(item.total_cents)}
                  </text>
                )}
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}
