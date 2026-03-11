"use client";

import type { AlignmentScore } from "@/lib/api/client";

interface Props {
  scores: AlignmentScore[];
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function industryLabel(industry: string): string {
  return industry.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ConfidencePip({ level }: { level: string }) {
  const colors: Record<string, string> = {
    high: "#4ade80", medium: "#fbbf24", low: "#333",
  };
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: colors[level] ?? "#333",
      }}
      title={`${level} confidence`}
    />
  );
}

function AlignmentBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          width: 96,
          height: 6,
          borderRadius: 3,
          overflow: "hidden",
          background: "#1c1c1c",
        }}
      >
        <div
          style={{
            height: "100%",
            borderRadius: 3,
            background: color,
            width: pct(Math.min(1, Math.max(0, value))),
          }}
        />
      </div>
      <span style={{ fontSize: 11, color: "#666", tabularNums: true } as React.CSSProperties}>
        {pct(value)}
      </span>
    </div>
  );
}

export function AlignmentHeatmap({ scores }: Props) {
  if (scores.length === 0) {
    return (
      <p style={{ fontSize: 13, color: "#333" }}>
        No significant correlations detected. Run the correlation pipeline after
        ingesting votes and finance data.
      </p>
    );
  }

  const sorted = [...scores].sort((a, b) => Math.abs(b.shift) - Math.abs(a.shift));

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #1c1c1c", background: "#0d0d0d" }}>
            <Th>Industry</Th>
            <Th>Before</Th>
            <Th>After</Th>
            <Th>Shift</Th>
            <Th align="center">Confidence</Th>
            <Th align="right">Votes</Th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => {
            const shiftPct = Math.round(s.shift * 100);
            const positive = s.shift >= 0;
            return (
              <tr key={s.id} style={{ borderBottom: "1px solid #1a1a1a" }}>
                <td style={{ padding: "10px 16px", fontWeight: 500, color: "var(--white)" }}>
                  {industryLabel(s.industry)}
                </td>
                <td style={{ padding: "10px 16px" }}>
                  <AlignmentBar value={s.before_score} color="#334f8d" />
                </td>
                <td style={{ padding: "10px 16px" }}>
                  <AlignmentBar value={s.after_score} color="var(--dem)" />
                </td>
                <td style={{ padding: "10px 16px" }}>
                  <span
                    style={{
                      display: "inline-block",
                      borderRadius: 4,
                      padding: "2px 6px",
                      fontSize: 11,
                      fontWeight: 700,
                      background: positive ? "#0d2a0d" : "#2a0d0d",
                      color: positive ? "#4ade80" : "#f87171",
                    }}
                  >
                    {positive ? "+" : ""}{shiftPct}pp
                  </span>
                </td>
                <td style={{ padding: "10px 16px", textAlign: "center" }}>
                  <ConfidencePip level={s.confidence} />
                </td>
                <td style={{ padding: "10px 16px", textAlign: "right", color: "#444" }}>
                  {s.evidence_count}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: string }) {
  return (
    <th
      style={{
        padding: "10px 16px",
        textAlign: align as "left" | "right" | "center",
        fontSize: 10,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.1em",
        color: "#444",
        fontFamily: "inherit",
      }}
    >
      {children}
    </th>
  );
}
