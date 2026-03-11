import { PARTY_LABEL } from "@/lib/api/client";

interface Props {
  party: string;
}

export function PartyBadge({ party }: Props) {
  const label = PARTY_LABEL[party] ?? party;
  const color =
    party === "D"
      ? "var(--dem)"
      : party === "R"
        ? "var(--rep)"
        : "#7c3aed";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: 20,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color,
        border: `1px solid ${color}`,
        background: "transparent",
      }}
    >
      {label}
    </span>
  );
}
