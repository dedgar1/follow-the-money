"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { IndustrySummary } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

// Readable industry labels
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

// Fixed color palette keyed by industry
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

interface Props {
  data: IndustrySummary[];
  size?: number;
}

export function DonutChart({ data, size = 280 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!el || !data.length) return;

    d3.select(el).selectAll("*").remove();

    const radius = size / 2 - 16;
    const inner = radius * 0.55;
    const total = d3.sum(data, (d) => d.total_cents);

    const svg = d3
      .select(el)
      .attr("viewBox", `0 0 ${size} ${size}`)
      .append("g")
      .attr("transform", `translate(${size / 2},${size / 2})`);

    const pie = d3.pie<IndustrySummary>().sort(null).value((d) => d.total_cents);
    const arc = d3
      .arc<d3.PieArcDatum<IndustrySummary>>()
      .innerRadius(inner)
      .outerRadius(radius);

    svg
      .selectAll("path")
      .data(pie(data))
      .join("path")
      .attr("d", arc)
      .attr("fill", (d) => colorFor(d.data.industry))
      .attr("stroke", "white")
      .attr("stroke-width", 2);

    // Center total
    svg
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "-0.4em")
      .attr("font-size", "11px")
      .attr("fill", "#6b7280")
      .text("Total raised");
    svg
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "1.1em")
      .attr("font-size", "16px")
      .attr("font-weight", "600")
      .attr("fill", "#111827")
      .text(formatDollars(total));
  }, [data, size]);

  if (!data.length) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-gray-400">
        No funding data available
      </div>
    );
  }

  return (
    <div>
      <svg ref={svgRef} className="w-full max-w-[280px]" />
      {/* Legend */}
      <ul className="mt-3 space-y-1">
        {data.slice(0, 6).map((d) => (
          <li key={d.industry} className="flex items-center gap-2 text-xs text-gray-600">
            <span
              className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-sm"
              style={{ background: colorFor(d.industry) }}
            />
            <span className="flex-1 truncate">{INDUSTRY_LABEL[d.industry] ?? d.industry}</span>
            <span className="font-medium text-gray-800">{formatDollars(d.total_cents)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
