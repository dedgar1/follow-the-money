"use client";

/**
 * D3 force-directed network graph — Sprint 6.
 * Shows the funding network centred on a rep or donor.
 *
 * Nodes:  reps (circles, party-coloured) · donors (diamonds, amber)
 * Edges:  FUNDED relationships (thickness ∝ amount)
 * Interaction: drag to reposition nodes, hover for tooltip
 */

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import type { NetworkNode, NetworkEdge } from "@/lib/api/client";
import { formatDollars } from "@/lib/api/client";

// D3 simulation augments nodes with position fields
type SimNode = NetworkNode & {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
};

type SimEdge = Omit<NetworkEdge, "source" | "target"> & {
  source: SimNode | string;
  target: SimNode | string;
};

interface TooltipState {
  x: number;
  y: number;
  node: NetworkNode;
}

function nodeColor(n: NetworkNode): string {
  if (n.type === "donor") return "#fbbf24";
  if (n.party === "D") return "#1a4fd6";
  if (n.party === "R") return "#e63022";
  return "#7c3aed";
}

function nodeRadius(n: NetworkNode): number {
  return n.is_center ? 20 : 12;
}

interface Props {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  height?: number;
}

export function NetworkGraph({ nodes, edges, height = 480 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  useEffect(() => {
    const svgEl = svgRef.current;
    const containerEl = containerRef.current;
    if (!svgEl || !containerEl || !nodes.length) return;

    const width = containerEl.clientWidth || 700;
    d3.select(svgEl).selectAll("*").remove();
    d3.select(svgEl).attr("width", width).attr("height", height);

    // Clone to avoid mutating props
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
    const simEdges: SimEdge[] = edges.map((e) => ({ ...e }));

    const maxCents = d3.max(edges, (e) => e.total_cents) ?? 1;
    const strokeW = d3.scaleLinear().domain([0, maxCents]).range([1, 5]);

    const svg = d3.select(svgEl);

    // Arrow marker for directed edges
    svg
      .append("defs")
      .append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 22)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "#d1d5db");

    const linkG = svg.append("g");
    const nodeG = svg.append("g");

    const link = linkG
      .selectAll<SVGLineElement, SimEdge>("line")
      .data(simEdges)
      .join("line")
      .attr("stroke", "#d1d5db")
      .attr("stroke-width", (e) => strokeW(e.total_cents))
      .attr("marker-end", "url(#arrow)");

    const nodeEl = nodeG
      .selectAll<SVGGElement, SimNode>("g")
      .data(simNodes)
      .join("g")
      .style("cursor", "pointer")
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .on("mouseenter", (event, d) => {
        const rect = svgEl.getBoundingClientRect();
        setTooltip({ x: event.clientX - rect.left + 12, y: event.clientY - rect.top - 8, node: d });
      })
      .on("mouseleave", () => setTooltip(null));

    // Node shape: diamond for donors, circle for reps
    nodeEl.each(function (d) {
      const g = d3.select(this);
      const r = nodeRadius(d);
      const color = nodeColor(d);
      const stroke = d.is_center ? "#111827" : "white";
      const sw = d.is_center ? 3 : 2;

      if (d.type === "donor") {
        // Diamond (rotated square)
        const s = r * 1.3;
        g.append("rect")
          .attr("width", s * 2)
          .attr("height", s * 2)
          .attr("x", -s)
          .attr("y", -s)
          .attr("transform", "rotate(45)")
          .attr("fill", color)
          .attr("stroke", stroke)
          .attr("stroke-width", sw);
      } else {
        g.append("circle")
          .attr("r", r)
          .attr("fill", color)
          .attr("stroke", stroke)
          .attr("stroke-width", sw);
      }

      // Label
      const shortLabel = d.label.length > 16 ? `${d.label.slice(0, 16)}…` : d.label;
      g.append("text")
        .attr("dy", r + 13)
        .attr("text-anchor", "middle")
        .attr("font-size", 10)
        .attr("fill", "#374151")
        .attr("pointer-events", "none")
        .text(shortLabel);
    });

    const sim = d3
      .forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(simEdges)
          .id((d) => d.id)
          .distance(110)
      )
      .force("charge", d3.forceManyBody<SimNode>().strength(-350))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide<SimNode>().radius((d) => nodeRadius(d) + 18));

    sim.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);

      nodeEl.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, height]);

  if (!nodes.length) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-gray-400">
        Network data unavailable — Neo4j must be running and seeded.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <svg ref={svgRef} className="w-full rounded border border-gray-100 bg-gray-50" />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 max-w-[200px] rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <p className="font-semibold text-gray-900">{tooltip.node.label}</p>
          <p className="mt-0.5 text-gray-500">
            {tooltip.node.type === "rep"
              ? `${tooltip.node.party} · ${tooltip.node.state} · ${tooltip.node.chamber}`
              : `${tooltip.node.donor_type}`}
          </p>
          {tooltip.node.is_center && (
            <p className="mt-1 rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">Center node</p>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full bg-[#1a4fd6]" />
          Democrat
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full bg-[#e63022]" />
          Republican
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 bg-[#fbbf24]"
            style={{ clipPath: "polygon(50% 0%,100% 50%,50% 100%,0% 50%)" }}
          />
          Donor
        </span>
        <span className="ml-auto text-gray-400">Drag nodes to reposition</span>
      </div>
    </div>
  );
}
