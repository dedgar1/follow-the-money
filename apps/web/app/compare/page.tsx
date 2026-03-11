import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import type { ComparisonResponse } from "@/lib/api/client";

interface Props {
  searchParams: Promise<{ ids?: string }>;
}

function partyColor(party: string): string {
  if (party === "D") return "var(--dem)";
  if (party === "R") return "var(--rep)";
  return "#7c3aed";
}

export default async function ComparePage({ searchParams }: Props) {
  const { ids } = await searchParams;

  if (!ids) return <SelectionPrompt />;

  const idList = ids.split(",").map((s) => s.trim()).filter(Boolean);
  if (idList.length < 2) return <SelectionPrompt />;

  let comparison: ComparisonResponse | null = null;
  let error: string | null = null;

  try {
    comparison = await api.compare(idList);
  } catch {
    error = "Could not load comparison — one or more representatives not found.";
  }

  if (error || !comparison) {
    return (
      <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto", padding: "48px 32px" }}>
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
            {error ?? "No comparison data available."}
          </div>
        </div>
      </main>
    );
  }

  const colCount = comparison.reps.length;

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 32px" }}>

        <Link
          href="/results"
          style={{ fontSize: 11, color: "#444", textDecoration: "none", textTransform: "uppercase", letterSpacing: "0.1em" }}
        >
          ← All Representatives
        </Link>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--white)", marginTop: 16 }}>
          Compare Representatives
        </h1>

        {/* Side-by-side profiles */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${colCount}, minmax(0, 1fr))`,
            gap: 16,
            marginTop: 24,
          }}
        >
          {comparison.reps.map((rep) => {
            const pc = partyColor(rep.party);
            return (
              <div
                key={rep.id}
                style={{
                  background: "#111",
                  border: "1px solid #1c1c1c",
                  borderRadius: 8,
                  overflow: "hidden",
                }}
              >
                {/* Party bar */}
                <div style={{ height: 3, background: pc }} />

                <div style={{ padding: "20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div style={{ minWidth: 0 }}>
                      <Link
                        href={`/rep/${rep.id}`}
                        style={{
                          display: "block",
                          fontWeight: 700,
                          fontSize: 16,
                          color: "var(--white)",
                          textDecoration: "none",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {rep.full_name}
                      </Link>
                      <p style={{ fontSize: 11, color: "#444", marginTop: 4 }}>
                        {CHAMBER_LABEL[rep.chamber] ?? rep.chamber} · {rep.state}
                        {rep.district ? ` · ${rep.district}` : ""}
                      </p>
                    </div>
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: pc,
                        flexShrink: 0,
                      }}
                    >
                      {rep.party === "D" ? "Dem" : rep.party === "R" ? "Rep" : rep.party}
                    </span>
                  </div>

                  <p style={{ marginTop: 12, fontSize: 18, fontWeight: 700, color: "var(--yellow)" }}>
                    {formatDollars(rep.total_raised_cents)}{" "}
                    <span style={{ fontSize: 11, fontWeight: 400, color: "#444" }}>raised</span>
                  </p>

                  {rep.top_industries.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <p style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", marginBottom: 8 }}>
                        Top Industries
                      </p>
                      <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                        {rep.top_industries.slice(0, 3).map((ind) => (
                          <li key={ind.industry} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11 }}>
                            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textTransform: "capitalize", color: "#888" }}>
                              {ind.industry.replace(/_/g, " ")}
                            </span>
                            <span style={{ flexShrink: 0, color: "#555" }}>{formatDollars(ind.total_cents)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {rep.alignment_scores.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <p style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", marginBottom: 8 }}>
                        Alignment Shift
                      </p>
                      {rep.alignment_scores.slice(0, 2).map((s) => (
                        <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, marginTop: 4 }}>
                          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textTransform: "capitalize", color: "#888" }}>
                            {s.industry.replace(/_/g, " ")}
                          </span>
                          <span
                            style={{
                              flexShrink: 0,
                              fontWeight: 700,
                              color: s.shift >= 0 ? "#4ade80" : "#f87171",
                            }}
                          >
                            {s.shift >= 0 ? "+" : ""}{(s.shift * 100).toFixed(0)}pp
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Shared donors */}
        {comparison.shared_donors.length > 0 ? (
          <section
            style={{
              marginTop: 32,
              background: "#111",
              border: "1px solid #1c1c1c",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            <div style={{ borderBottom: "1px solid #1c1c1c", padding: "16px 24px" }}>
              <h2 style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#555" }}>
                Shared Donors ({comparison.shared_donors.length})
              </h2>
              <p style={{ fontSize: 11, color: "#333", marginTop: 4 }}>
                Donors who have contributed to all representatives being compared
              </p>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid #1c1c1c", background: "#0d0d0d" }}>
                    <Th>Donor</Th>
                    <Th>Industry</Th>
                    {comparison.reps.map((rep) => (
                      <Th key={rep.id} align="right">{rep.full_name.split(" ").pop()}</Th>
                    ))}
                    <Th align="right">Total</Th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.shared_donors.map((d) => {
                    const total = Object.values(d.amounts).reduce((a, b) => a + b, 0);
                    return (
                      <tr key={d.donor_id} style={{ borderBottom: "1px solid #1a1a1a" }}>
                        <td style={{ padding: "10px 24px" }}>
                          <Link
                            href={`/donor/${d.donor_id}`}
                            style={{ color: "var(--white)", textDecoration: "none", fontWeight: 500 }}
                          >
                            {d.donor_name}
                          </Link>
                        </td>
                        <td style={{ padding: "10px 24px", fontSize: 11, textTransform: "capitalize", color: "#555" }}>
                          {d.industry ? d.industry.replace(/_/g, " ") : "—"}
                        </td>
                        {comparison.reps.map((rep) => (
                          <td key={rep.id} style={{ padding: "10px 24px", textAlign: "right", color: "#888" }}>
                            {formatDollars(d.amounts[rep.id] ?? 0)}
                          </td>
                        ))}
                        <td style={{ padding: "10px 24px", textAlign: "right", fontWeight: 700, color: "var(--yellow)" }}>
                          {formatDollars(total)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <div
            style={{
              marginTop: 32,
              border: "1px dashed #222",
              borderRadius: 8,
              padding: 48,
              textAlign: "center",
              fontSize: 13,
              color: "#333",
            }}
          >
            No shared donors found between these representatives.
          </div>
        )}

        <p style={{ marginTop: 24, fontSize: 11, color: "#333" }}>
          Funding data sourced from FEC filings. Correlation ≠ causation.{" "}
          <Link href="/docs/methodology" style={{ color: "#444", textDecoration: "underline" }}>
            See methodology.
          </Link>
        </p>
      </div>
    </main>
  );
}

function SelectionPrompt() {
  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "48px 32px" }}>
        <Link href="/" style={{ fontSize: 12, color: "#555", textDecoration: "none" }}>← Back</Link>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--white)", marginTop: 16 }}>
          Compare Representatives
        </h1>
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
          <p style={{ fontWeight: 500, fontSize: 14 }}>
            Navigate to a representative profile and click Compare to start.
          </p>
          <p style={{ marginTop: 8, fontSize: 12 }}>
            Or use the URL directly:{" "}
            <code
              style={{
                background: "#1c1c1c",
                border: "1px solid #333",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 11,
                color: "#888",
              }}
            >
              /compare?ids=REP001,REP002
            </code>
          </p>
        </div>
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
