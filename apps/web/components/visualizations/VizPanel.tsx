"use client";

import { useState } from "react";
import Link from "next/link";
import type { IndustrySummary, TopDonorSummary, AlignmentScore } from "@/lib/api/client";
import { formatDollars, exportJsonUrl } from "@/lib/api/client";
import { DonutChart } from "./DonutChart";
import { TopDonorsBar } from "./TopDonorsBar";
import { Treemap } from "./Treemap";
import { NetworkGraph } from "./NetworkGraph";
import type { NetworkNode, NetworkEdge } from "@/lib/api/client";

type Tab = "donut" | "bar" | "treemap" | "network";

interface Props {
  repId: string;
  repName: string;
  totalRaisedCents: number;
  smallDonorCents: number;
  foreignConnectedCents: number;
  industries: IndustrySummary[];
  donors: TopDonorSummary[];
  network: { nodes: NetworkNode[]; edges: NetworkEdge[] };
  alignmentScores: AlignmentScore[];
}

export function VizPanel({
  repId,
  repName,
  totalRaisedCents,
  smallDonorCents,
  foreignConnectedCents,
  industries,
  donors,
  network,
  alignmentScores,
}: Props) {
  const [tab, setTab] = useState<Tab>("donut");

  const tabs: { id: Tab; label: string }[] = [
    { id: "donut", label: "Industries" },
    { id: "bar", label: "Donors" },
    { id: "treemap", label: "Treemap" },
    { id: "network", label: "Network" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 24 }}>

      {/* Main viz area */}
      <div>
        {/* Tabs */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid #1c1c1c",
            marginBottom: 24,
          }}
        >
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: "10px 16px",
                fontSize: 11,
                fontWeight: tab === t.id ? 700 : 400,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: tab === t.id ? "var(--white)" : "#444",
                background: "none",
                border: "none",
                borderBottom: tab === t.id ? "2px solid var(--white)" : "2px solid transparent",
                cursor: "pointer",
                fontFamily: "inherit",
                marginBottom: -1,
                transition: "color 0.15s",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Viz content */}
        <div>
          {tab === "donut" && (
            <div style={{ display: "flex", justifyContent: "center" }}>
              <DonutChart data={industries} />
            </div>
          )}
          {tab === "bar" && <TopDonorsBar data={donors} />}
          {tab === "treemap" && (
            <Treemap data={industries} total={totalRaisedCents} />
          )}
          {tab === "network" && (
            <div>
              <p style={{ fontSize: 11, color: "#444", marginBottom: 12 }}>
                Donors (◆) who fund this rep and other reps funded by the same donors
              </p>
              <NetworkGraph nodes={network.nodes} edges={network.edges} />
            </div>
          )}
        </div>
      </div>

      {/* Sidebar */}
      <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>

        {/* Funding Breakdown */}
        <div
          style={{
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            padding: "16px",
          }}
        >
          <p
            style={{
              fontSize: 10,
              color: "#444",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: 12,
            }}
          >
            Funding Breakdown
          </p>
          <FundingBreakdownRow
            label="Small Donors <$200"
            value={smallDonorCents > 0 ? formatDollars(smallDonorCents) : "—"}
            note={smallDonorCents === 0 ? "no data" : undefined}
          />
          <FundingBreakdownRow label="PAC Contributions" value={formatDollars(totalRaisedCents)} />
          <FundingBreakdownRow
            label="Foreign-Connected"
            value={foreignConnectedCents > 0 ? formatDollars(foreignConnectedCents) : "—"}
            note={foreignConnectedCents === 0 ? "no data" : undefined}
          />
        </div>

        {/* Top Donors */}
        {donors.length > 0 && (
          <div
            style={{
              background: "#111",
              border: "1px solid #1c1c1c",
              borderRadius: 8,
              padding: "16px",
            }}
          >
            <p
              style={{
                fontSize: 10,
                color: "#444",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: 10,
              }}
            >
              Top Donors
            </p>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
              {donors.slice(0, 5).map((d) => (
                <li
                  key={d.donor_id}
                  style={{ display: "flex", justifyContent: "space-between", gap: 8 }}
                >
                  <Link
                    href={`/donor/${d.donor_id}`}
                    style={{
                      fontSize: 12,
                      color: "var(--white)",
                      textDecoration: "none",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      flex: 1,
                    }}
                  >
                    {d.donor_name}
                  </Link>
                  <span style={{ fontSize: 11, color: "var(--yellow)", whiteSpace: "nowrap" }}>
                    {formatDollars(d.total_cents)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Share & Export */}
        <div
          style={{
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            padding: "16px",
          }}
        >
          <p
            style={{
              fontSize: 10,
              color: "#444",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: 10,
            }}
          >
            Share & Export
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <SidebarActionLink
              href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/v1/export/${repId}.csv`}
              label="Export CSV"
              download
            />
            <SidebarActionLink
              href={exportJsonUrl(repId)}
              label="Export JSON"
              download
            />
          </div>
        </div>

        {/* Compare */}
        <Link
          href={`/compare?ids=${repId}`}
          style={{
            display: "block",
            padding: "10px 14px",
            background: "#1c1c1c",
            border: "1px solid #333",
            borderRadius: 8,
            fontSize: 12,
            color: "#888",
            textDecoration: "none",
            textAlign: "center",
            letterSpacing: "0.05em",
          }}
        >
          Compare with another rep →
        </Link>
      </aside>
    </div>
  );
}

function FundingBreakdownRow({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "4px 0",
        borderBottom: "1px solid #1a1a1a",
        fontSize: 11,
      }}
    >
      <span style={{ color: "#666" }}>{label}</span>
      <span style={{ color: note ? "#333" : "var(--white)", fontSize: note ? 10 : 11 }}>
        {note ? `[${note}]` : value}
      </span>
    </div>
  );
}

function SidebarActionLink({
  href,
  label,
  download,
}: {
  href: string;
  label: string;
  download?: boolean;
}) {
  return (
    <a
      href={href}
      download={download}
      style={{
        display: "block",
        padding: "7px 12px",
        background: "#1c1c1c",
        border: "1px solid #333",
        borderRadius: 4,
        fontSize: 11,
        color: "#888",
        textDecoration: "none",
        letterSpacing: "0.05em",
      }}
    >
      {label}
    </a>
  );
}
