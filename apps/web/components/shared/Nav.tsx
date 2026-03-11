"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function Nav() {
  const router = useRouter();
  const [q, setQ] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = q.trim();
    if (trimmed) router.push(`/results?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <nav
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        height: 56,
        background: "var(--black)",
        borderBottom: "2px solid var(--yellow)",
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 24,
      }}
    >
      {/* Logo */}
      <Link
        href="/"
        style={{
          fontFamily: "var(--font-geist-mono), monospace",
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: "0.12em",
          color: "var(--yellow)",
          textDecoration: "none",
          whiteSpace: "nowrap",
          textTransform: "uppercase",
        }}
      >
        Follow the Money
      </Link>

      {/* Search */}
      <form onSubmit={handleSearch} style={{ flex: 1, maxWidth: 480, margin: "0 auto" }}>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search representatives, donors..."
          style={{
            width: "100%",
            background: "#1c1c1c",
            border: "1px solid #444",
            borderRadius: 4,
            padding: "6px 12px",
            color: "var(--white)",
            fontSize: 12,
            fontFamily: "inherit",
            outline: "none",
          }}
        />
      </form>

      {/* Nav links */}
      <div style={{ display: "flex", gap: 20, fontSize: 12, letterSpacing: "0.05em" }}>
        <Link
          href="/results?chamber=house"
          style={{ color: "#888", textDecoration: "none", textTransform: "uppercase" }}
        >
          House
        </Link>
        <Link
          href="/results?chamber=senate"
          style={{ color: "#888", textDecoration: "none", textTransform: "uppercase" }}
        >
          Senate
        </Link>
        <Link
          href="/docs/methodology"
          style={{ color: "#888", textDecoration: "none", textTransform: "uppercase" }}
        >
          Methodology
        </Link>
      </div>
    </nav>
  );
}
