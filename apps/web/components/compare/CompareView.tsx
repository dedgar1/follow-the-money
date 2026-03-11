"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import type { RepSummary, SearchResult, ComparisonResponse } from "@/lib/api/client";

const MAX_SLOTS = 3;

function partyColor(party: string) {
  if (party === "D") return "var(--dem)";
  if (party === "R") return "var(--rep)";
  return "#7c3aed";
}

// ── Slot selector ──────────────────────────────────────────────────────────────

interface SlotProps {
  rep: RepSummary | null;
  slotIndex: number;
  onSelect: (rep: RepSummary) => void;
  onRemove: () => void;
}

function Slot({ rep, slotIndex, onSelect, onRemove }: SlotProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced search
  useEffect(() => {
    if (query.length < 2) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api.search(query);
        setResults(r.filter((x) => x.type === "rep").slice(0, 8));
      } catch { setResults([]); }
      finally { setLoading(false); }
    }, 280);
    return () => clearTimeout(t);
  }, [query]);

  const handleSelect = (r: SearchResult) => {
    onSelect({
      id: r.id,
      full_name: r.name,
      party: r.party ?? "O",
      chamber: r.chamber ?? "",
      state: r.state ?? "",
      district: null,
      bioguide_id: null,
    });
    setQuery("");
    setResults([]);
    setOpen(false);
  };

  // Filled slot
  if (rep) {
    const pc = partyColor(rep.party);
    return (
      <div
        style={{
          flex: 1,
          minWidth: 0,
          background: "#111",
          border: `1px solid ${pc}`,
          borderTop: `3px solid ${pc}`,
          borderRadius: 8,
          padding: "20px 20px 16px",
          position: "relative",
        }}
      >
        <button
          onClick={onRemove}
          aria-label="Remove"
          style={{
            position: "absolute",
            top: 10,
            right: 10,
            background: "none",
            border: "none",
            color: "#444",
            cursor: "pointer",
            fontSize: 16,
            lineHeight: 1,
            padding: 4,
            fontFamily: "inherit",
          }}
        >
          ×
        </button>

        <p style={{ fontSize: 9, fontWeight: 700, letterSpacing: "0.15em", textTransform: "uppercase", color: pc, marginBottom: 6 }}>
          {rep.party === "D" ? "Democrat" : rep.party === "R" ? "Republican" : rep.party}
        </p>
        <p style={{ fontSize: 15, fontWeight: 700, color: "var(--white)", lineHeight: 1.3, paddingRight: 20 }}>
          {rep.full_name}
        </p>
        <p style={{ fontSize: 11, color: "#444", marginTop: 5 }}>
          {CHAMBER_LABEL[rep.chamber] ?? rep.chamber} · {rep.state}
          {rep.district ? ` · ${rep.district}` : ""}
        </p>
      </div>
    );
  }

  // Empty slot
  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        minWidth: 0,
        background: "#0d0d0d",
        border: "1px dashed #222",
        borderRadius: 8,
        padding: "20px",
        position: "relative",
      }}
    >
      <p style={{ fontSize: 10, color: "#333", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>
        Representative {slotIndex + 1}
      </p>

      <div style={{ position: "relative" }}>
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Search by name…"
          style={{
            width: "100%",
            background: "#111",
            border: "1px solid #1c1c1c",
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 12,
            color: "var(--white)",
            fontFamily: "inherit",
            outline: "none",
          }}
        />

        {open && (query.length >= 2) && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              background: "#111",
              border: "1px solid #222",
              borderRadius: 6,
              zIndex: 100,
              maxHeight: 240,
              overflowY: "auto",
            }}
          >
            {loading && (
              <p style={{ padding: "10px 14px", fontSize: 11, color: "#444" }}>Searching…</p>
            )}
            {!loading && results.length === 0 && (
              <p style={{ padding: "10px 14px", fontSize: 11, color: "#444" }}>No representatives found.</p>
            )}
            {results.map((r) => {
              const pc = r.party === "D" ? "var(--dem)" : r.party === "R" ? "var(--rep)" : "#555";
              return (
                <button
                  key={r.id}
                  onClick={() => handleSelect(r)}
                  style={{
                    width: "100%",
                    background: "none",
                    border: "none",
                    borderBottom: "1px solid #1a1a1a",
                    padding: "10px 14px",
                    textAlign: "left",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    fontFamily: "inherit",
                  }}
                >
                  <span
                    style={{
                      width: 3,
                      height: 28,
                      borderRadius: 2,
                      background: pc,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ display: "block", fontSize: 12, color: "var(--white)", fontWeight: 500 }}>
                      {r.name}
                    </span>
                    <span style={{ display: "block", fontSize: 10, color: "#444", marginTop: 2 }}>
                      {r.chamber === "house" ? "House" : r.chamber === "senate" ? "Senate" : r.chamber ?? ""} · {r.state}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Comparison rows ────────────────────────────────────────────────────────────

function CompareRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr style={{ borderBottom: "1px solid #1a1a1a" }}>
      <td
        style={{
          padding: "12px 20px",
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "#444",
          whiteSpace: "nowrap",
          background: "#0d0d0d",
          width: 160,
        }}
      >
        {label}
      </td>
      {children}
    </tr>
  );
}

function CompareCell({ children }: { children: React.ReactNode }) {
  return (
    <td style={{ padding: "12px 20px", fontSize: 12, color: "var(--white)", verticalAlign: "top" }}>
      {children}
    </td>
  );
}

// ── Main view ──────────────────────────────────────────────────────────────────

export function CompareView() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [slots, setSlots] = useState<(RepSummary | null)[]>([null, null, null]);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Pre-populate from URL ?ids=
  useEffect(() => {
    const ids = searchParams.get("ids");
    if (!ids) return;
    const idList = ids.split(",").map((s) => s.trim()).filter(Boolean).slice(0, MAX_SLOTS);
    if (idList.length < 2) return;

    Promise.all(idList.map((id) => api.getRepresentative(id).catch(() => null))).then((reps) => {
      setSlots([
        reps[0] ?? null,
        reps[1] ?? null,
        reps[2] ?? null,
      ]);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filled = slots.filter(Boolean) as RepSummary[];

  // Fetch comparison whenever 2+ slots filled
  useEffect(() => {
    if (filled.length < 2) {
      setComparison(null);
      return;
    }
    const ids = filled.map((r) => r.id);
    // Sync URL
    router.replace(`/compare?ids=${ids.join(",")}`, { scroll: false });

    setLoadingComparison(true);
    api.compare(ids)
      .then(setComparison)
      .catch(() => setComparison(null))
      .finally(() => setLoadingComparison(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slots]);

  const handleSelect = (index: number, rep: RepSummary) => {
    // Prevent duplicates
    if (slots.some((s) => s?.id === rep.id)) return;
    setSlots((prev) => {
      const next = [...prev];
      next[index] = rep;
      return next;
    });
  };

  const handleRemove = (index: number) => {
    setSlots((prev) => {
      const next = [...prev];
      next[index] = null;
      return next;
    });
  };

  const showThirdSlot = filled.length >= 2 || slots[2] !== null;

  return (
    <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "40px 32px" }}>

        <Link
          href="/results"
          style={{ fontSize: 11, color: "#444", textDecoration: "none", textTransform: "uppercase", letterSpacing: "0.1em" }}
        >
          ← All Representatives
        </Link>

        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--white)", letterSpacing: "-0.02em", marginTop: 16 }}>
          Compare Representatives
        </h1>
        <p style={{ fontSize: 12, color: "#444", marginTop: 6 }}>
          Search and select up to 3 representatives to compare side-by-side.
        </p>

        {/* ── Selector slots ─────────────────────────────────────────────────── */}
        <div style={{ display: "flex", gap: 12, marginTop: 28, alignItems: "stretch" }}>
          <Slot rep={slots[0]} slotIndex={0} onSelect={(r) => handleSelect(0, r)} onRemove={() => handleRemove(0)} />
          <Slot rep={slots[1]} slotIndex={1} onSelect={(r) => handleSelect(1, r)} onRemove={() => handleRemove(1)} />
          {showThirdSlot && (
            <Slot rep={slots[2]} slotIndex={2} onSelect={(r) => handleSelect(2, r)} onRemove={() => handleRemove(2)} />
          )}
        </div>

        {filled.length < 2 && (
          <p style={{ marginTop: 16, fontSize: 11, color: "#333", textAlign: "center" }}>
            Select at least 2 representatives to see the comparison.
          </p>
        )}

        {/* ── Comparison table ───────────────────────────────────────────────── */}
        {loadingComparison && (
          <div style={{ marginTop: 40, textAlign: "center", fontSize: 12, color: "#444" }}>
            Loading comparison…
          </div>
        )}

        {!loadingComparison && comparison && (
          <>
            {/* Column headers */}
            <div style={{ marginTop: 40, overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #1c1c1c" }}>
                    <th style={{ width: 160, background: "#0d0d0d" }} />
                    {comparison.reps.map((rep) => {
                      const pc = partyColor(rep.party);
                      return (
                        <th
                          key={rep.id}
                          style={{
                            padding: "0 20px 16px",
                            textAlign: "left",
                            verticalAlign: "bottom",
                            borderTop: `3px solid ${pc}`,
                          }}
                        >
                          <Link
                            href={`/rep/${rep.id}`}
                            style={{ textDecoration: "none", display: "block" }}
                          >
                            <span style={{ display: "block", fontSize: 9, fontWeight: 700, letterSpacing: "0.15em", textTransform: "uppercase", color: pc, marginBottom: 4 }}>
                              {rep.party === "D" ? "Democrat" : rep.party === "R" ? "Republican" : rep.party}
                            </span>
                            <span style={{ display: "block", fontSize: 14, fontWeight: 700, color: "var(--white)" }}>
                              {rep.full_name}
                            </span>
                            <span style={{ display: "block", fontSize: 11, color: "#444", marginTop: 3 }}>
                              {CHAMBER_LABEL[rep.chamber] ?? rep.chamber} · {rep.state}
                            </span>
                          </Link>
                        </th>
                      );
                    })}
                  </tr>
                </thead>

                <tbody>
                  {/* Total raised */}
                  <CompareRow label="Total Raised">
                    {comparison.reps.map((rep) => (
                      <CompareCell key={rep.id}>
                        <span style={{ fontSize: 18, fontWeight: 700, color: "var(--yellow)" }}>
                          {formatDollars(rep.total_raised_cents)}
                        </span>
                      </CompareCell>
                    ))}
                  </CompareRow>

                  {/* Top industries */}
                  <CompareRow label="Top Industries">
                    {comparison.reps.map((rep) => (
                      <CompareCell key={rep.id}>
                        {rep.top_industries.length === 0 ? (
                          <span style={{ color: "#333" }}>—</span>
                        ) : (
                          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
                            {rep.top_industries.slice(0, 4).map((ind) => (
                              <li key={ind.industry} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                                <span style={{ fontSize: 11, color: "#888", textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {ind.industry.replace(/_/g, " ")}
                                </span>
                                <span style={{ fontSize: 11, color: "#555", flexShrink: 0 }}>
                                  {formatDollars(ind.total_cents)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </CompareCell>
                    ))}
                  </CompareRow>

                  {/* Top donors */}
                  <CompareRow label="Top Donors">
                    {comparison.reps.map((rep) => (
                      <CompareCell key={rep.id}>
                        {rep.top_donors.length === 0 ? (
                          <span style={{ color: "#333" }}>—</span>
                        ) : (
                          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
                            {rep.top_donors.slice(0, 3).map((d) => (
                              <li key={d.donor_id} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                                <Link
                                  href={`/donor/${d.donor_id}`}
                                  style={{ fontSize: 11, color: "#888", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textDecoration: "none" }}
                                >
                                  {d.donor_name}
                                </Link>
                                <span style={{ fontSize: 11, color: "#555", flexShrink: 0 }}>
                                  {formatDollars(d.total_cents)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </CompareCell>
                    ))}
                  </CompareRow>

                  {/* Alignment shifts */}
                  <CompareRow label="Alignment Shifts">
                    {comparison.reps.map((rep) => (
                      <CompareCell key={rep.id}>
                        {rep.alignment_scores.length === 0 ? (
                          <span style={{ fontSize: 11, color: "#333" }}>No significant shifts</span>
                        ) : (
                          <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                            {rep.alignment_scores.slice(0, 3).map((s) => (
                              <li key={s.id} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                                <span style={{ fontSize: 11, color: "#888", textTransform: "capitalize", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {s.industry.replace(/_/g, " ")}
                                </span>
                                <span style={{ fontSize: 11, fontWeight: 700, flexShrink: 0, color: s.shift >= 0 ? "#4ade80" : "#f87171" }}>
                                  {s.shift >= 0 ? "+" : ""}{(s.shift * 100).toFixed(0)}pp
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </CompareCell>
                    ))}
                  </CompareRow>
                </tbody>
              </table>
            </div>

            {/* Shared donors */}
            <section
              style={{
                marginTop: 32,
                background: "#111",
                border: "1px solid #1c1c1c",
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              <div style={{ borderBottom: "1px solid #1c1c1c", padding: "14px 24px" }}>
                <h2 style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#555" }}>
                  Shared Donors ({comparison.shared_donors.length})
                </h2>
                {comparison.shared_donors.length > 0 && (
                  <p style={{ fontSize: 11, color: "#333", marginTop: 3 }}>
                    Donors who fund all selected representatives
                  </p>
                )}
              </div>

              {comparison.shared_donors.length === 0 ? (
                <div style={{ padding: "32px 24px", textAlign: "center", fontSize: 12, color: "#333" }}>
                  No donors in common between these representatives.
                </div>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #1c1c1c", background: "#0d0d0d" }}>
                        <th style={{ padding: "10px 24px", textAlign: "left", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", fontFamily: "inherit" }}>Donor</th>
                        <th style={{ padding: "10px 24px", textAlign: "left", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", fontFamily: "inherit" }}>Industry</th>
                        {comparison.reps.map((rep) => (
                          <th key={rep.id} style={{ padding: "10px 24px", textAlign: "right", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", fontFamily: "inherit" }}>
                            {rep.full_name.split(" ").slice(-1)[0]}
                          </th>
                        ))}
                        <th style={{ padding: "10px 24px", textAlign: "right", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em", color: "#444", fontFamily: "inherit" }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparison.shared_donors.map((d) => {
                        const total = Object.values(d.amounts).reduce((a, b) => a + b, 0);
                        return (
                          <tr key={d.donor_id} style={{ borderBottom: "1px solid #1a1a1a" }}>
                            <td style={{ padding: "10px 24px" }}>
                              <Link href={`/donor/${d.donor_id}`} style={{ color: "var(--white)", textDecoration: "none", fontWeight: 500 }}>
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
              )}
            </section>

            <p style={{ marginTop: 20, fontSize: 11, color: "#333" }}>
              Funding data sourced from FEC filings. Correlation ≠ causation.{" "}
              <Link href="/docs/methodology" style={{ color: "#444", textDecoration: "underline" }}>
                See methodology.
              </Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}
