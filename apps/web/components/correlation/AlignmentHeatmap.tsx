"use client";

/**
 * AlignmentHeatmap — shows before/after voting alignment per industry.
 *
 * Each row = one industry.  Two bars (before / after) show alignment scores
 * (0–100%).  A coloured shift badge shows the direction of change.
 */

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
  const styles: Record<string, string> = {
    high:   "bg-green-500",
    medium: "bg-yellow-400",
    low:    "bg-gray-300",
  };
  const cls = styles[level] ?? "bg-gray-300";
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${cls}`}
      title={`${level} confidence`}
    />
  );
}

function AlignmentBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: pct(Math.min(1, Math.max(0, value))) }}
        />
      </div>
      <span className="w-8 text-right text-xs tabular-nums text-gray-600">
        {pct(value)}
      </span>
    </div>
  );
}

export function AlignmentHeatmap({ scores }: Props) {
  if (scores.length === 0) {
    return (
      <p className="text-sm text-gray-400">
        No significant correlations detected. Run the correlation pipeline after
        ingesting votes and finance data.
      </p>
    );
  }

  // Sort by absolute shift descending
  const sorted = [...scores].sort((a, b) => Math.abs(b.shift) - Math.abs(a.shift));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
            <th className="px-4 py-2 text-left font-medium">Industry</th>
            <th className="px-4 py-2 text-left font-medium">Before</th>
            <th className="px-4 py-2 text-left font-medium">After</th>
            <th className="px-4 py-2 text-left font-medium">Shift</th>
            <th className="px-4 py-2 text-center font-medium">Confidence</th>
            <th className="px-4 py-2 text-right font-medium">Votes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.map((s) => {
            const shiftPct = Math.round(s.shift * 100);
            const shiftPositive = s.shift >= 0;
            const shiftColor = shiftPositive
              ? "text-green-700 bg-green-50"
              : "text-red-700 bg-red-50";

            return (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-800">
                  {industryLabel(s.industry)}
                </td>
                <td className="px-4 py-3">
                  <AlignmentBar value={s.before_score} color="bg-blue-300" />
                </td>
                <td className="px-4 py-3">
                  <AlignmentBar value={s.after_score} color="bg-blue-600" />
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-xs font-semibold tabular-nums ${shiftColor}`}
                  >
                    {shiftPositive ? "+" : ""}
                    {shiftPct}pp
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <ConfidencePip level={s.confidence} />
                </td>
                <td className="px-4 py-3 text-right text-gray-500">
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
