"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ZipForm() {
  const router = useRouter();
  const [zip, setZip] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const z = zip.trim();
    if (/^\d{5}$/.test(z)) router.push(`/results?zip=${z}`);
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8 }}>
      <input
        type="text"
        value={zip}
        onChange={(e) => setZip(e.target.value)}
        placeholder="Enter ZIP code (e.g. 90210)"
        maxLength={5}
        style={{
          flex: 1,
          background: "#1c1c1c",
          border: "1px solid #333",
          borderRadius: 4,
          padding: "10px 14px",
          color: "var(--white)",
          fontSize: 13,
          fontFamily: "inherit",
          outline: "none",
        }}
      />
      <button
        type="submit"
        style={{
          background: "var(--yellow)",
          color: "#0a0a0a",
          border: "none",
          borderRadius: 4,
          padding: "10px 20px",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        Find
      </button>
    </form>
  );
}
