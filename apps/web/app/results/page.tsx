import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import type { RepSummary, SearchResult } from "@/lib/api/client";

interface Props {
  searchParams: Promise<{
    q?: string;
    state?: string;
    chamber?: string;
    zip?: string;
  }>;
}

async function fetchResults(params: {
  q?: string;
  state?: string;
  chamber?: string;
  zip?: string;
}): Promise<{ reps: RepSummary[]; searchResults: SearchResult[]; error?: string }> {
  try {
    if (params.zip) {
      const reps = await api.getZipReps(params.zip);
      return { reps, searchResults: [] };
    }
    if (params.q?.trim()) {
      const searchResults = await api.search(params.q.trim());
      return { reps: [], searchResults };
    }
    const reps = await api.listRepresentatives({
      state: params.state,
      chamber: params.chamber,
    });
    return { reps, searchResults: [] };
  } catch {
    return { reps: [], searchResults: [], error: "Failed to load results" };
  }
}

export default async function ResultsPage({ searchParams }: Props) {
  const { q, state, chamber, zip } = await searchParams;
  const { reps, searchResults, error } = await fetchResults({ q, state, chamber, zip });

  // Build filter label
  const filterParts: string[] = [];
  if (zip) filterParts.push(`ZIP ${zip}`);
  else if (q) filterParts.push(`"${q}"`);
  else {
    if (state) filterParts.push(state.toUpperCase());
    if (chamber) filterParts.push(CHAMBER_LABEL[chamber] ?? chamber);
  }
  const filterLabel = filterParts.join(" · ") || "All Representatives";

  const totalResults = searchResults.length > 0 ? searchResults.length : reps.length;

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "40px 32px" }}>

        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <p style={{ fontSize: 11, color: "#555", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {filterLabel}
          </p>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginTop: 4 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--white)" }}>
              {totalResults > 0
                ? `${totalResults} result${totalResults !== 1 ? "s" : ""}`
                : error ?? "No results found"}
            </h1>
            {/* Chamber filter chips */}
            <div style={{ display: "flex", gap: 8 }}>
              <FilterChip href="/results?chamber=house" label="House" active={chamber === "house"} />
              <FilterChip href="/results?chamber=senate" label="Senate" active={chamber === "senate"} />
              {(chamber || state || zip) && (
                <FilterChip href="/results" label="Clear" active={false} />
              )}
            </div>
          </div>
        </div>

        {/* Search results (reps + donors mixed) */}
        {searchResults.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 16,
            }}
          >
            {searchResults.map((r) => (
              <SearchResultCard key={`${r.type}-${r.id}`} result={r} />
            ))}
          </div>
        )}

        {/* Rep results grid */}
        {reps.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 16,
            }}
          >
            {reps.map((rep) => (
              <DarkRepCard key={rep.id} rep={rep} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {totalResults === 0 && !error && (
          <div
            style={{
              textAlign: "center",
              padding: "80px 0",
              color: "#444",
              border: "1px dashed #222",
              borderRadius: 8,
            }}
          >
            <p style={{ fontSize: 14 }}>No representatives found.</p>
            <p style={{ fontSize: 12, marginTop: 8 }}>
              Try a different filter or{" "}
              <Link href="/" style={{ color: "var(--yellow)", textDecoration: "none" }}>
                return to the map
              </Link>
              .
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

// ── Cards ─────────────────────────────────────────────────────────────────────

function DarkRepCard({ rep }: { rep: RepSummary }) {
  const partyColor = rep.party === "D" ? "var(--dem)" : rep.party === "R" ? "var(--rep)" : "#7c3aed";
  const partyLabel = rep.party === "D" ? "Democrat" : rep.party === "R" ? "Republican" : rep.party;

  return (
    <Link
      href={`/rep/${rep.id}`}
      style={{ textDecoration: "none", display: "block" }}
    >
      <div
        style={{
          background: "#111",
          border: "1px solid #1c1c1c",
          borderRadius: 8,
          overflow: "hidden",
          transition: "border-color 0.15s",
        }}
      >
        {/* Party bar */}
        <div style={{ height: 3, background: partyColor }} />

        <div style={{ padding: "16px 18px 18px" }}>
          {/* Party badge */}
          <span
            style={{
              fontSize: 9,
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: partyColor,
            }}
          >
            {partyLabel}
          </span>

          {/* Name */}
          <p
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "var(--white)",
              marginTop: 6,
              lineHeight: 1.2,
            }}
          >
            {rep.full_name}
          </p>

          {/* Meta */}
          <p style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
            {rep.state}
            {rep.district ? ` · ${rep.district}` : ""}
            {" · "}
            {CHAMBER_LABEL[rep.chamber] ?? rep.chamber}
          </p>

          {/* Amount — only shown when profile data is available (RepProfile, not RepSummary) */}
          {"total_raised_cents" in rep && (rep as { total_raised_cents: number }).total_raised_cents > 0 && (
            <p
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: "var(--yellow)",
                marginTop: 12,
                letterSpacing: "-0.02em",
              }}
            >
              {formatDollars((rep as { total_raised_cents: number }).total_raised_cents)}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}

function SearchResultCard({ result }: { result: SearchResult }) {
  const href = result.type === "rep" ? `/rep/${result.id}` : `/donor/${result.id}`;
  const typeLabel = result.type === "rep" ? "Representative" : "Donor";
  const typeColor = result.type === "rep" ? "var(--yellow)" : "#888";

  return (
    <Link href={href} style={{ textDecoration: "none", display: "block" }}>
      <div
        style={{
          background: "#111",
          border: "1px solid #1c1c1c",
          borderRadius: 8,
          padding: "16px 18px",
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: typeColor,
          }}
        >
          {typeLabel}
        </span>
        <p style={{ fontSize: 16, fontWeight: 700, color: "var(--white)", marginTop: 6 }}>
          {result.name}
        </p>
        <p style={{ fontSize: 11, color: "#555", marginTop: 4 }}>
          {[result.state, result.chamber, result.party, result.donor_type]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
    </Link>
  );
}

function FilterChip({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      style={{
        padding: "4px 12px",
        background: active ? "var(--yellow)" : "#1c1c1c",
        border: "1px solid #333",
        borderRadius: 20,
        fontSize: 11,
        color: active ? "#0a0a0a" : "#888",
        textDecoration: "none",
        fontWeight: active ? 700 : 400,
        letterSpacing: "0.05em",
      }}
    >
      {label}
    </Link>
  );
}
