import { Suspense } from "react";
import Link from "next/link";
import { USMap } from "@/components/map/USMap";
import { api, formatDollars, type PlatformStats, type TickerItem } from "@/lib/api/client";
import { ZipForm } from "@/components/shared/ZipForm";

async function fetchStats(): Promise<PlatformStats> {
  try {
    return await api.getStats();
  } catch {
    return { total_reps: 0, total_donors: 0, total_raised_cents: 0, total_correlations: 0 };
  }
}

async function fetchTicker(): Promise<TickerItem[]> {
  try {
    return await api.getTicker(30);
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [stats, tickerItems] = await Promise.all([fetchStats(), fetchTicker()]);

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>

      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 48,
          maxWidth: 1200,
          margin: "0 auto",
          padding: "64px 32px 48px",
        }}
      >
        {/* Left — headline + ZIP */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 24,
          }}
          className="fade-up s1"
        >
          <div>
            <p
              style={{
                fontSize: 11,
                letterSpacing: "0.2em",
                textTransform: "uppercase",
                color: "var(--yellow)",
                marginBottom: 12,
              }}
            >
              Campaign Finance Intelligence
            </p>
            <h1
              style={{
                fontSize: 48,
                fontWeight: 700,
                lineHeight: 1.05,
                color: "var(--white)",
                letterSpacing: "-0.02em",
              }}
            >
              Follow the Money
            </h1>
            <p style={{ marginTop: 16, fontSize: 15, color: "#888", lineHeight: 1.6 }}>
              See who funds your representatives.
              Track how donations shape votes.
            </p>
          </div>

          {/* ZIP input */}
          <div>
            <p style={{ fontSize: 11, color: "#555", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Find your representatives
            </p>
            <Suspense>
              <ZipForm />
            </Suspense>
          </div>

          {/* Discover chips */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <DiscoverChip href="/results?chamber=senate" label="Senate" />
            <DiscoverChip href="/results?chamber=house" label="House" />
            <DiscoverChip href="/results?state=CA" label="California" />
            <DiscoverChip href="/results?state=TX" label="Texas" />
            <DiscoverChip href="/results?state=NY" label="New York" />
          </div>
        </div>

        {/* Right — US Map */}
        <div className="fade-up s2">
          <p
            style={{
              fontSize: 10,
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              color: "#444",
              marginBottom: 12,
            }}
          >
            Click a state to explore representatives
          </p>
          <Suspense fallback={<div style={{ height: 380, background: "#111", borderRadius: 8 }} />}>
            <USMap />
          </Suspense>
        </div>
      </section>

      {/* ── Ticker ───────────────────────────────────────────────────────────── */}
      <div
        style={{
          borderTop: "1px solid #1c1c1c",
          borderBottom: "1px solid #1c1c1c",
          background: "#0d0d0d",
          overflow: "hidden",
          padding: "10px 0",
        }}
      >
        <div className="ticker-track" style={{ display: "flex", gap: 48, whiteSpace: "nowrap" }}>
          {(tickerItems.length > 0 ? buildTickerLabels(tickerItems) : FALLBACK_TICKER)
            .concat(tickerItems.length > 0 ? buildTickerLabels(tickerItems) : FALLBACK_TICKER)
            .map((item, i) => (
              <span key={i} style={{ fontSize: 11, color: "#555", letterSpacing: "0.05em" }}>
                <span style={{ color: "var(--yellow)" }}>◆</span>&nbsp;{item}
              </span>
            ))}
        </div>
      </div>

      {/* ── Stats row ────────────────────────────────────────────────────────── */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          maxWidth: 1200,
          margin: "0 auto",
          padding: "0 32px",
          borderBottom: "1px solid #1c1c1c",
        }}
        className="stats-row"
      >
        <StatBox
          value={stats.total_reps > 0 ? stats.total_reps.toLocaleString() : "—"}
          label="Representatives tracked"
        />
        <StatBox
          value={stats.total_raised_cents > 0 ? formatDollars(stats.total_raised_cents) : "—"}
          label="Total donations tracked"
        />
        <StatBox
          value={stats.total_donors > 0 ? stats.total_donors.toLocaleString() : "—"}
          label="Donors indexed"
        />
        <StatBox
          value={stats.total_correlations > 0 ? stats.total_correlations.toLocaleString() : "—"}
          label="Alignment correlations"
        />
      </section>
    </main>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DiscoverChip({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      style={{
        padding: "5px 12px",
        background: "#1c1c1c",
        border: "1px solid #333",
        borderRadius: 20,
        fontSize: 11,
        color: "#888",
        textDecoration: "none",
        letterSpacing: "0.05em",
        transition: "border-color 0.15s",
      }}
    >
      {label}
    </Link>
  );
}

function StatBox({
  value,
  label,
  note,
}: {
  value: string;
  label: string;
  note?: string;
}) {
  return (
    <div
      style={{
        padding: "32px 24px",
        borderRight: "1px solid #1c1c1c",
      }}
    >
      <p style={{ fontSize: 32, fontWeight: 700, color: "var(--yellow)", lineHeight: 1 }}>
        {value}
      </p>
      <p style={{ fontSize: 11, color: "#555", marginTop: 6, textTransform: "uppercase", letterSpacing: "0.1em" }}>
        {label}
      </p>
      {note && (
        <p style={{ fontSize: 10, color: "#333", marginTop: 4 }}>[{note}]</p>
      )}
    </div>
  );
}

const FALLBACK_TICKER = [
  "Latest FEC filings updated nightly",
  "Explore donor networks across industries",
  "Compare representatives side-by-side",
  "See voting alignment before and after donations",
  "Correlation ≠ causation — see methodology",
  "Source: FEC, Congress.gov, Senate.gov",
];

function buildTickerLabels(items: TickerItem[]): string[] {
  return items.map((item) => {
    const dollars = formatDollars(item.amount_cents);
    const date = item.contribution_date ? ` · ${item.contribution_date}` : "";
    return `${item.contributor_name} — ${dollars}${date}`;
  });
}
