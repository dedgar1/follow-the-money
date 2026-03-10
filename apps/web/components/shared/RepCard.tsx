import Link from "next/link";
import type { RepSummary } from "@/lib/api/client";
import { CHAMBER_LABEL } from "@/lib/api/client";
import { PartyBadge } from "./PartyBadge";

interface Props {
  rep: RepSummary;
}

export function RepCard({ rep }: Props) {
  const partyBorder = rep.party === "D"
    ? "border-l-[var(--color-democrat)]"
    : rep.party === "R"
      ? "border-l-[var(--color-republican)]"
      : "border-l-[var(--color-independent)]";

  return (
    <Link
      href={`/rep/${rep.id}`}
      className={`block rounded-lg border border-gray-200 border-l-4 ${partyBorder} bg-white p-4 shadow-sm transition hover:shadow-md`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-gray-900">{rep.full_name}</p>
          <p className="mt-0.5 text-sm text-gray-500">
            {rep.state}{rep.district ? ` · ${rep.district}` : ""} · {CHAMBER_LABEL[rep.chamber] ?? rep.chamber}
          </p>
        </div>
        <PartyBadge party={rep.party} />
      </div>
    </Link>
  );
}
