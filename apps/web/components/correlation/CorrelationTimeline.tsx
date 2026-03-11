"use client";

/**
 * CorrelationTimeline — side-by-side before/after view for one industry.
 *
 * Shows the 24-month "before" and "after" windows around the major donation
 * event, with alignment scores visualised as filled arcs.
 */

import type { AlignmentScore } from "@/lib/api/client";

interface Props {
  score: AlignmentScore;
}

function ScoreArc({ value, label }: { value: number; label: string }) {
  // Simple SVG arc gauge
  const r = 36;
  const cx = 48;
  const cy = 48;
  const circumference = Math.PI * r; // half-circle
  const filled = circumference * value;
  const pct = Math.round(value * 100);

  // Arc from left to right (bottom half hidden — we show top half as gauge)
  const startX = cx - r;
  const startY = cy;
  const endX = cx + r;
  const endY = cy;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={96} height={56} aria-label={`${label}: ${pct}%`}>
        {/* Track */}
        <path
          d={`M ${startX} ${startY} A ${r} ${r} 0 0 1 ${endX} ${endY}`}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={`M ${startX} ${startY} A ${r} ${r} 0 0 1 ${endX} ${endY}`}
          fill="none"
          stroke="#2563eb"
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          style={{ transition: "stroke-dasharray 0.4s ease" }}
        />
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fontSize={13}
          fontWeight={600}
          fill="#1f2937"
        >
          {pct}%
        </text>
      </svg>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  );
}

export function CorrelationTimeline({ score }: Props) {
  const shiftPct = Math.round(score.shift * 100);
  const shiftPositive = score.shift >= 0;
  const shiftColor = shiftPositive ? "text-green-700" : "text-red-700";
  const industryLabel = score.industry
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
        {industryLabel}
      </p>

      {/* Before → Event → After layout */}
      <div className="flex items-center justify-around gap-2">
        <ScoreArc value={score.before_score} label="Before" />

        {/* Event marker */}
        <div className="flex flex-col items-center gap-1 text-center">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100">
            <span className="text-sm">💰</span>
          </div>
          <span className="text-[10px] text-gray-400">Major donation</span>
          <span className={`text-sm font-bold ${shiftColor}`}>
            {shiftPositive ? "+" : ""}
            {shiftPct}pp
          </span>
        </div>

        <ScoreArc value={score.after_score} label="After" />
      </div>

      <div className="mt-3 flex justify-between text-[10px] text-gray-400">
        <span>{score.evidence_count} votes analysed</span>
        <span>p = {score.p_value.toFixed(3)}</span>
        <span className="capitalize">{score.confidence} confidence</span>
      </div>
    </div>
  );
}
