import { PARTY_LABEL } from "@/lib/api/client";

interface Props {
  party: string;
}

export function PartyBadge({ party }: Props) {
  const label = PARTY_LABEL[party] ?? party;
  const cls =
    party === "D"
      ? "bg-blue-100 text-blue-800"
      : party === "R"
        ? "bg-red-100 text-red-800"
        : "bg-purple-100 text-purple-800";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {label}
    </span>
  );
}
