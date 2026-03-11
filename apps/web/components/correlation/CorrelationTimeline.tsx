"use client";

import type { AlignmentScore } from "@/lib/api/client";

interface Props {
  score: AlignmentScore;
}

function ScoreArc({ value, label }: { value: number; label: string }) {
  const r = 36;
  const cx = 48;
  const cy = 48;
  const circumference = Math.PI * r;
  const filled = circumference * value;
  const pct = Math.round(value * 100);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={96} height={56} aria-label={`${label}: ${pct}%`}>
        {/* Track */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="#1c1c1c"
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none"
          stroke="var(--dem)"
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
          fill="var(--white)"
        >
          {pct}%
        </text>
      </svg>
      <span style={{ fontSize: 10, color: "#555" }}>{label}</span>
    </div>
  );
}

export function CorrelationTimeline({ score }: Props) {
  const shiftPct = Math.round(score.shift * 100);
  const positive = score.shift >= 0;
  const shiftColor = positive ? "#4ade80" : "#f87171";
  const industryLabel = score.industry
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      style={{
        borderRadius: 8,
        border: "1px solid #1c1c1c",
        background: "#0d0d0d",
        padding: 16,
      }}
    >
      <p
        style={{
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "#444",
          marginBottom: 12,
        }}
      >
        {industryLabel}
      </p>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", gap: 8 }}>
        <ScoreArc value={score.before_score} label="Before" />

        {/* Event marker */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, textAlign: "center" }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "#1c1c1c",
              border: "1px solid #333",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
            }}
          >
            $
          </div>
          <span style={{ fontSize: 9, color: "#333" }}>Major donation</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: shiftColor }}>
            {positive ? "+" : ""}{shiftPct}pp
          </span>
        </div>

        <ScoreArc value={score.after_score} label="After" />
      </div>

      <div
        style={{
          marginTop: 12,
          display: "flex",
          justifyContent: "space-between",
          fontSize: 10,
          color: "#333",
        }}
      >
        <span>{score.evidence_count} votes</span>
        <span>p = {score.p_value.toFixed(3)}</span>
        <span style={{ textTransform: "capitalize" }}>{score.confidence}</span>
      </div>
    </div>
  );
}
