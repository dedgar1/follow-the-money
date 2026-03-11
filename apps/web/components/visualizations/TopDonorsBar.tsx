/**
 * Horizontal bar chart for top donors — pure React SVG, server-renderable.
 */

import type { TopDonorSummary } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

interface Props {
  data: TopDonorSummary[];
}

const BAR_HEIGHT = 28;
const GAP = 8;
const LABEL_W = 190;
const AMOUNT_W = 72;
const BAR_MAX_W = 220;
const SVG_W = LABEL_W + BAR_MAX_W + AMOUNT_W + 8;

export function TopDonorsBar({ data }: Props) {
  if (!data.length) {
    return (
      <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "#444" }}>
        No donor data available
      </div>
    );
  }

  const maxCents = Math.max(...data.map((d) => d.total_cents));
  const svgH = data.length * (BAR_HEIGHT + GAP) + GAP;

  return (
    <svg
      viewBox={`0 0 ${SVG_W} ${svgH}`}
      width={SVG_W}
      height={svgH}
      className="w-full"
      aria-label="Top donors bar chart"
    >
      {data.map((d, i) => {
        const y = GAP + i * (BAR_HEIGHT + GAP);
        const barW = Math.round((d.total_cents / maxCents) * BAR_MAX_W);
        const truncated =
          d.donor_name.length > 26 ? `${d.donor_name.slice(0, 26)}…` : d.donor_name;

        return (
          <g key={d.donor_id}>
            {/* Name */}
            <text
              x={LABEL_W - 8}
              y={y + BAR_HEIGHT / 2}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize={11}
              fill="#888"
            >
              {truncated}
            </text>

            {/* Bar background */}
            <rect
              x={LABEL_W}
              y={y + 4}
              width={BAR_MAX_W}
              height={BAR_HEIGHT - 8}
              rx={3}
              fill="#1c1c1c"
            />

            {/* Bar fill */}
            {barW > 0 && (
              <rect
                x={LABEL_W}
                y={y + 4}
                width={barW}
                height={BAR_HEIGHT - 8}
                rx={3}
                fill="var(--yellow)"
              />
            )}

            {/* Amount */}
            <text
              x={LABEL_W + BAR_MAX_W + 6}
              y={y + BAR_HEIGHT / 2}
              dominantBaseline="middle"
              fontSize={11}
              fill="#555"
            >
              {formatDollars(d.total_cents)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
