"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { TopDonorSummary } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

interface Props {
  data: TopDonorSummary[];
}

export function TopDonorsBar({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!el || !data.length) return;

    const margin = { top: 4, right: 90, bottom: 4, left: 200 };
    const barHeight = 30;
    const height = data.length * barHeight + margin.top + margin.bottom;
    const width = 520;
    const innerW = width - margin.left - margin.right;

    d3.select(el).selectAll("*").remove();

    const svg = d3
      .select(el)
      .attr("viewBox", `0 0 ${width} ${height}`);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.total_cents) ?? 1])
      .range([0, innerW]);

    const y = d3
      .scaleBand()
      .domain(data.map((d) => d.donor_id))
      .range([0, height - margin.top - margin.bottom])
      .padding(0.3);

    // Bars
    g.selectAll("rect")
      .data(data)
      .join("rect")
      .attr("y", (d) => y(d.donor_id)!)
      .attr("width", (d) => x(d.total_cents))
      .attr("height", y.bandwidth())
      .attr("fill", "#3b82f6")
      .attr("rx", 3);

    // Donor name (left)
    g.selectAll(".name")
      .data(data)
      .join("text")
      .attr("class", "name")
      .attr("x", -8)
      .attr("y", (d) => y(d.donor_id)! + y.bandwidth() / 2)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#374151")
      .text((d) =>
        d.donor_name.length > 28 ? `${d.donor_name.slice(0, 28)}…` : d.donor_name
      );

    // Amount (right)
    g.selectAll(".amount")
      .data(data)
      .join("text")
      .attr("class", "amount")
      .attr("x", (d) => x(d.total_cents) + 6)
      .attr("y", (d) => y(d.donor_id)! + y.bandwidth() / 2)
      .attr("dominant-baseline", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#6b7280")
      .text((d) => formatDollars(d.total_cents));
  }, [data]);

  if (!data.length) {
    return (
      <div className="flex h-[200px] items-center justify-center text-sm text-gray-400">
        No donor data available
      </div>
    );
  }

  return <svg ref={svgRef} className="w-full" />;
}
