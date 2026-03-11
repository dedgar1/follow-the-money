import { notFound } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import { NetworkGraph } from "@/components/visualizations/NetworkGraph";

interface Props {
  params: Promise<{ id: string }>;
}

const DONOR_TYPE_LABEL: Record<string, string> = {
  individual: "Individual",
  pac: "PAC",
  corporation: "Corporation",
  union: "Union",
  other: "Other",
};

function partyColor(party: string): string {
  if (party === "D") return "var(--dem)";
  if (party === "R") return "var(--rep)";
  return "#7c3aed";
}

export default async function DonorDetailPage({ params }: Props) {
  const { id } = await params;

  let donor: Awaited<ReturnType<typeof api.getDonor>> | null;
  let recipients: Awaited<ReturnType<typeof api.getDonorRecipients>>;
  let network: Awaited<ReturnType<typeof api.getDonorNetwork>>;

  try {
    [donor, recipients, network] = await Promise.all([
      api.getDonor(id),
      api.getDonorRecipients(id),
      api.getDonorNetwork(id).catch(() => ({ nodes: [], edges: [] })),
    ]);
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    if (status === 404) notFound();
    donor = null;
    recipients = [];
    network = { nodes: [], edges: [] };
  }

  if (!donor) {
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
            Donor not found or API unavailable.
          </div>
        </div>
      </main>
    );
  }

  const democrats  = recipients.filter((r) => r.party === "D");
  const republicans = recipients.filter((r) => r.party === "R");
  const demTotal   = democrats.reduce((s, r) => s + r.total_cents, 0);
  const repTotal   = republicans.reduce((s, r) => s + r.total_cents, 0);
  const grandTotal = recipients.reduce((s, r) => s + r.total_cents, 0);

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ borderBottom: "1px solid #1c1c1c", padding: "40px 0 32px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto", padding: "0 32px" }}>
          <Link
            href="/results"
            style={{ fontSize: 11, color: "#444", textDecoration: "none", textTransform: "uppercase", letterSpacing: "0.1em" }}
          >
            ← Search
          </Link>

          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginTop: 20, flexWrap: "wrap" }}>
            <div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.15em",
                  textTransform: "uppercase",
                  color: "#555",
                }}
              >
                {DONOR_TYPE_LABEL[donor.donor_type] ?? donor.donor_type}
                {donor.industry && ` · ${donor.industry}`}
                {donor.state && ` · ${donor.state}`}
              </span>

              <h1
                style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: "var(--white)",
                  letterSpacing: "-0.02em",
                  marginTop: 8,
                  lineHeight: 1.1,
                }}
              >
                {donor.name}
              </h1>
            </div>

            <div style={{ textAlign: "right" }}>
              <p style={{ fontSize: 11, color: "#444", textTransform: "uppercase", letterSpacing: "0.1em" }}>Total Given</p>
              <p
                style={{
                  fontSize: 32,
                  fontWeight: 700,
                  color: "var(--yellow)",
                  letterSpacing: "-0.02em",
                  marginTop: 4,
                }}
              >
                {formatDollars(donor.total_given_cents)}
              </p>
            </div>
          </div>

          {/* Party split bar */}
          {grandTotal > 0 && (
            <div style={{ marginTop: 24, maxWidth: 480 }}>
              <p style={{ fontSize: 10, color: "#444", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.1em" }}>
                Giving by party
              </p>
              <div
                style={{
                  display: "flex",
                  height: 6,
                  borderRadius: 3,
                  overflow: "hidden",
                  background: "#1c1c1c",
                }}
              >
                {demTotal > 0 && (
                  <div style={{ width: `${(demTotal / grandTotal) * 100}%`, background: "var(--dem)" }} />
                )}
                {repTotal > 0 && (
                  <div style={{ width: `${(repTotal / grandTotal) * 100}%`, background: "var(--rep)" }} />
                )}
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: 11, color: "#555" }}>
                <span>
                  <span style={{ color: "var(--dem)", fontWeight: 700 }}>Dem</span>{" "}
                  {formatDollars(demTotal)} ({democrats.length})
                </span>
                <span>
                  <span style={{ color: "var(--rep)", fontWeight: 700 }}>Rep</span>{" "}
                  {formatDollars(repTotal)} ({republicans.length})
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "32px 32px 48px" }}>

        {/* ── Recipients ─────────────────────────────────────────────────── */}
        <section
          style={{
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <div style={{ borderBottom: "1px solid #1c1c1c", padding: "16px 24px" }}>
            <h2
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "#555",
              }}
            >
              Recipients ({recipients.length})
            </h2>
          </div>

          {recipients.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center", fontSize: 13, color: "#333" }}>
              No recipients found for this donor.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1c1c1c", background: "#0d0d0d" }}>
                    <Th>Representative</Th>
                    <Th>Party</Th>
                    <Th>State · Chamber</Th>
                    <Th align="right">Total Given</Th>
                  </tr>
                </thead>
                <tbody>
                  {recipients.map((r) => (
                    <tr key={r.rep_id} style={{ borderBottom: "1px solid #1a1a1a" }}>
                      <td style={{ padding: "10px 24px" }}>
                        <Link
                          href={`/rep/${r.rep_id}`}
                          style={{ color: "var(--white)", textDecoration: "none", fontWeight: 500 }}
                        >
                          {r.rep_name}
                        </Link>
                      </td>
                      <td style={{ padding: "10px 24px" }}>
                        <span style={{ fontSize: 10, fontWeight: 700, color: partyColor(r.party), textTransform: "uppercase", letterSpacing: "0.1em" }}>
                          {r.party === "D" ? "Dem" : r.party === "R" ? "Rep" : r.party}
                        </span>
                      </td>
                      <td style={{ padding: "10px 24px", color: "#555" }}>
                        {r.state} · {CHAMBER_LABEL[r.chamber] ?? r.chamber}
                      </td>
                      <td style={{ padding: "10px 24px", textAlign: "right", color: "var(--yellow)", fontWeight: 600 }}>
                        {formatDollars(r.total_cents)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* ── Network ────────────────────────────────────────────────────── */}
        <section
          style={{
            marginTop: 24,
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 8,
            padding: 24,
          }}
        >
          <h2
            style={{
              fontSize: 11,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "#555",
              marginBottom: 8,
            }}
          >
            Funding Network
          </h2>
          <p style={{ fontSize: 11, color: "#333", marginBottom: 16 }}>
            Reps (●) funded by this donor and other donors (◆) who fund the same reps
          </p>
          <NetworkGraph nodes={network.nodes} edges={network.edges} />
        </section>

        <p style={{ marginTop: 24, fontSize: 11, color: "#333" }}>
          Funding data sourced from FEC filings. Correlation ≠ causation.
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
