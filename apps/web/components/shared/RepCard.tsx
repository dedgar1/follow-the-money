import Link from "next/link";
import type { RepSummary } from "@/lib/api/client";
import { CHAMBER_LABEL } from "@/lib/api/client";

interface Props {
  rep: RepSummary;
}

export function RepCard({ rep }: Props) {
  const partyColor =
    rep.party === "D"
      ? "var(--dem)"
      : rep.party === "R"
        ? "var(--rep)"
        : "#7c3aed";
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
        <div style={{ height: 3, background: partyColor }} />
        <div style={{ padding: "14px 16px" }}>
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
          <p style={{ fontWeight: 600, fontSize: 14, color: "var(--white)", marginTop: 4 }}>
            {rep.full_name}
          </p>
          <p style={{ fontSize: 11, color: "#555", marginTop: 2 }}>
            {rep.state}{rep.district ? ` · ${rep.district}` : ""} · {CHAMBER_LABEL[rep.chamber] ?? rep.chamber}
          </p>
        </div>
      </div>
    </Link>
  );
}
