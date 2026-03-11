import { notFound } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import type { AlignmentScore, VoteRecord } from "@/lib/api/client";
import { VizPanel } from "@/components/visualizations/VizPanel";
import { AlignmentHeatmap } from "@/components/correlation/AlignmentHeatmap";
import { CorrelationTimeline } from "@/components/correlation/CorrelationTimeline";

interface Props {
  params: Promise<{ id: string }>;
}

function partyColor(party: string): string {
  if (party === "D") return "var(--dem)";
  if (party === "R") return "var(--rep)";
  return "#7c3aed";
}

function partyLabel(party: string): string {
  if (party === "D") return "Democrat";
  if (party === "R") return "Republican";
  return party;
}

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function VoteBadge({ position }: { position: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    yes:        { bg: "#0d2a0d", color: "#4ade80" },
    no:         { bg: "#2a0d0d", color: "#f87171" },
    abstain:    { bg: "#2a1f00", color: "#fbbf24" },
    not_voting: { bg: "#1a1a1a", color: "#555" },
  };
  const labels: Record<string, string> = {
    yes: "Yes", no: "No", abstain: "Abstain", not_voting: "Not Voting",
  };
  const style = styles[position] ?? styles.not_voting;
  return (
    <span
      style={{
        display: "inline-block",
        borderRadius: 20,
        padding: "2px 8px",
        fontSize: 10,
        fontWeight: 700,
        background: style.bg,
        color: style.color,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
      }}
    >
      {labels[position] ?? position}
    </span>
  );
}

export default async function RepProfilePage({ params }: Props) {
  const { id } = await params;

  let rep: Awaited<ReturnType<typeof api.getRepresentative>> | null;
  let network: Awaited<ReturnType<typeof api.getRepNetwork>>;
  let votes: VoteRecord[];
  let correlations: AlignmentScore[];

  try {
    [rep, network, votes, correlations] = await Promise.all([
      api.getRepresentative(id),
      api.getRepNetwork(id).catch(() => ({ nodes: [], edges: [] })),
      api.getRepVotes(id).catch(() => []),
      api.getRepCorrelations(id).catch(() => []),
    ]);
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    if (status === 404) notFound();
    rep = null;
    network = { nodes: [], edges: [] };
    votes = [];
    correlations = [];
  }

  if (!rep) {
    return (
      <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "48px 32px" }}>
          <Link href="/" style={{ fontSize: 12, color: "#555", textDecoration: "none" }}>← Back</Link>
          <div
            style={{
              marginTop: 32,
              border: "1px dashed #222",
              borderRadius: 8,
              padding: 48,
              textAlign: "center",
              color: "#444",
            }}
          >
            Representative not found or API unavailable.
          </div>
        </div>
      </main>
    );
  }

  const pc = partyColor(rep.party);

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>

      {/* ── Profile header ─────────────────────────────────────────────────── */}
      <div
        style={{
          borderBottom: "1px solid #1c1c1c",
          padding: "40px 0 32px",
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "0 32px" }}>
          <Link
            href="/results"
            style={{ fontSize: 11, color: "#444", textDecoration: "none", textTransform: "uppercase", letterSpacing: "0.1em" }}
          >
            ← All Representatives
          </Link>

          <div style={{ display: "flex", alignItems: "flex-start", gap: 24, marginTop: 20 }}>
            {/* Initials box */}
            <div
              style={{
                width: 72,
                height: 72,
                borderRadius: 8,
                background: "#111",
                border: `2px solid ${pc}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 22,
                fontWeight: 700,
                color: pc,
                flexShrink: 0,
              }}
            >
              {initials(rep.full_name)}
            </div>

            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.15em",
                    textTransform: "uppercase",
                    color: pc,
                  }}
                >
                  {partyLabel(rep.party)}
                </span>
                <span style={{ fontSize: 11, color: "#333" }}>
                  {CHAMBER_LABEL[rep.chamber] ?? rep.chamber}
                </span>
                <span style={{ fontSize: 11, color: "#333" }}>
                  {rep.state}{rep.district ? ` · ${rep.district}` : ""}
                </span>
              </div>

              <h1
                style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: "var(--white)",
                  letterSpacing: "-0.02em",
                  lineHeight: 1.1,
                  marginTop: 8,
                }}
              >
                {rep.full_name}
              </h1>

              <p
                style={{
                  fontSize: 24,
                  fontWeight: 700,
                  color: "var(--yellow)",
                  marginTop: 8,
                  letterSpacing: "-0.02em",
                }}
              >
                {formatDollars(rep.total_raised_cents)}{" "}
                <span style={{ fontSize: 12, color: "#444", fontWeight: 400 }}>raised</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Viz panel ──────────────────────────────────────────────────────── */}
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 32px 0" }}>
        <VizPanel
          repId={rep.id}
          repName={rep.full_name}
          totalRaisedCents={rep.total_raised_cents}
          smallDonorCents={rep.small_donor_cents ?? 0}
          industries={rep.top_industries}
          donors={rep.top_donors}
          network={network}
          alignmentScores={correlations}
        />
      </div>

      {/* ── Voting record ──────────────────────────────────────────────────── */}
      <div style={{ maxWidth: 1100, margin: "32px auto 0", padding: "0 32px" }}>
        <section
          style={{
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              borderBottom: "1px solid #1c1c1c",
              padding: "16px 24px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "#555",
              }}
            >
              Voting Record ({votes.length})
            </h2>
          </div>

          {votes.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center", fontSize: 13, color: "#333" }}>
              No vote data available — run the ingest pipeline to populate.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1c1c1c", background: "#0d0d0d" }}>
                    <Th>Bill</Th>
                    <Th>Industry</Th>
                    <Th align="center">Vote</Th>
                    <Th align="right">Date</Th>
                  </tr>
                </thead>
                <tbody>
                  {votes.map((v) => (
                    <tr
                      key={v.vote_id}
                      style={{ borderBottom: "1px solid #1a1a1a" }}
                    >
                      <td style={{ padding: "10px 24px", maxWidth: 300 }}>
                        <span style={{ color: "var(--white)", fontWeight: 500 }}>{v.bill_title}</span>
                        {v.bill_id && (
                          <span style={{ marginLeft: 8, fontSize: 10, color: "#444", textTransform: "uppercase" }}>
                            {v.bill_id}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "10px 24px" }}>
                        {v.industries.length > 0 ? (
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              background: "#1c1c1c",
                              borderRadius: 12,
                              fontSize: 10,
                              color: "#888",
                              textTransform: "capitalize",
                            }}
                          >
                            {v.industries[0].replace(/_/g, " ")}
                          </span>
                        ) : (
                          <span style={{ color: "#333", fontSize: 10 }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: "10px 24px", textAlign: "center" }}>
                        <VoteBadge position={v.position} />
                      </td>
                      <td style={{ padding: "10px 24px", textAlign: "right", color: "#444" }}>
                        {v.voted_at}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* ── Alignment correlations ─────────────────────────────────────────── */}
      <div style={{ maxWidth: 1100, margin: "24px auto 0", padding: "0 32px" }}>
        <section
          style={{
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              borderBottom: "1px solid #1c1c1c",
              padding: "16px 24px",
            }}
          >
            <h2
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "#555",
              }}
            >
              Donor-Industry Alignment ({correlations.length})
            </h2>
            <p style={{ fontSize: 11, color: "#333", marginTop: 4 }}>
              Voting alignment before and after significant donations. Correlation ≠ causation.{" "}
              <Link href="/docs/methodology" style={{ color: "#555", textDecoration: "underline" }}>
                Methodology
              </Link>
            </p>
          </div>

          <div style={{ padding: 24 }}>
            <AlignmentHeatmap scores={correlations} />
          </div>

          {correlations.length > 0 && (
            <div style={{ borderTop: "1px solid #1c1c1c", padding: 24 }}>
              <p
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  color: "#333",
                  marginBottom: 16,
                }}
              >
                Before / After Detail
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 16,
                }}
              >
                {correlations.slice(0, 6).map((s) => (
                  <CorrelationTimeline key={s.id} score={s} />
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Disclaimer */}
      <div style={{ maxWidth: 1100, margin: "24px auto 48px", padding: "0 32px" }}>
        <p style={{ fontSize: 11, color: "#333" }}>
          Funding data sourced from FEC filings. Correlation ≠ causation.{" "}
          <Link href="/docs/methodology" style={{ color: "#444", textDecoration: "underline" }}>
            See methodology.
          </Link>
        </p>
      </div>
    </main>
  );
}

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
}) {
  return (
    <th
      style={{
        padding: "10px 24px",
        textAlign: align,
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
