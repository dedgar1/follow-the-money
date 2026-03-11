import { Suspense } from "react";
import Link from "next/link";
import { USMap } from "@/components/map/USMap";
import { api } from "@/lib/api/client";
import { ZipForm } from "@/components/shared/ZipForm";

async function fetchRepCount(): Promise<number> {
  try {
    const reps = await api.listRepresentatives({});
    return reps.length;
  } catch {
    return 0;
  }
}

export default async function HomePage() {
  const repCount = await fetchRepCount();

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
      {/* TODO Sprint 10: replace with live latest-filings feed */}
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
          {TICKER_ITEMS.concat(TICKER_ITEMS).map((item, i) => (
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
      >
        <StatBox
          value={repCount > 0 ? repCount.toLocaleString() : "535"}
          label="Representatives tracked"
          note={repCount === 0 ? "placeholder" : undefined}
        />
        {/* TODO Sprint 10: wire these to live DB aggregates */}
        <StatBox value="$8.9B" label="Total donations tracked" note="placeholder" />
        <StatBox value="12,847" label="Donors indexed" note="placeholder" />
        <StatBox value="2,341" label="Alignment correlations" note="placeholder" />
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

const TICKER_ITEMS = [
  "Latest FEC filings updated nightly",
  "Explore donor networks across industries",
  "Compare representatives side-by-side",
  "See voting alignment before and after donations",
  "Correlation ≠ causation — see methodology",
  "Source: FEC, Congress.gov, Senate.gov",
];
