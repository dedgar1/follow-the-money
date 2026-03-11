import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import type { ComparisonResponse } from "@/lib/api/client";
import { PartyBadge } from "@/components/shared/PartyBadge";

interface Props {
  searchParams: Promise<{ ids?: string }>;
}

export default async function ComparePage({ searchParams }: Props) {
  const { ids } = await searchParams;

  if (!ids) {
    return <SelectionPrompt />;
  }

  const idList = ids.split(",").map((s) => s.trim()).filter(Boolean);
  if (idList.length < 2) {
    return <SelectionPrompt />;
  }

  let comparison: ComparisonResponse | null = null;
  let error: string | null = null;

  try {
    comparison = await api.compare(idList);
  } catch {
    error = "Could not load comparison — one or more representatives not found.";
  }

  if (error || !comparison) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-5xl px-6 py-12">
          <Link href="/" className="text-sm text-blue-600 hover:underline">← Back</Link>
          <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-400">
            {error ?? "No comparison data available."}
          </div>
        </div>
      </main>
    );
  }

  const colCount = comparison.reps.length;

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← All representatives
        </Link>
        <h1 className="mt-4 text-2xl font-bold text-gray-900">Compare Representatives</h1>

        {/* Side-by-side profiles */}
        <div
          className="mt-6 grid gap-4"
          style={{ gridTemplateColumns: `repeat(${colCount}, minmax(0, 1fr))` }}
        >
          {comparison.reps.map((rep) => (
            <div key={rep.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link
                    href={`/rep/${rep.id}`}
                    className="block truncate font-bold text-gray-900 hover:text-blue-600"
                  >
                    {rep.full_name}
                  </Link>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {CHAMBER_LABEL[rep.chamber] ?? rep.chamber} · {rep.state}
                    {rep.district ? ` · ${rep.district}` : ""}
                  </p>
                </div>
                <PartyBadge party={rep.party} />
              </div>

              <p className="mt-3 text-sm font-semibold text-gray-700">
                {formatDollars(rep.total_raised_cents)}{" "}
                <span className="font-normal text-gray-400">raised</span>
              </p>

              {rep.top_industries.length > 0 && (
                <div className="mt-4">
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                    Top Industries
                  </p>
                  <ul className="space-y-1.5">
                    {rep.top_industries.slice(0, 3).map((ind) => (
                      <li key={ind.industry} className="flex items-center gap-2 text-xs">
                        <span className="flex-1 truncate capitalize text-gray-600">
                          {ind.industry.replace(/_/g, " ")}
                        </span>
                        <span className="shrink-0 text-gray-500">{formatDollars(ind.total_cents)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {rep.alignment_scores.length > 0 && (
                <div className="mt-4">
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                    Alignment Shift
                  </p>
                  {rep.alignment_scores.slice(0, 2).map((s) => (
                    <div key={s.id} className="mt-1 flex items-center gap-2 text-xs">
                      <span className="flex-1 truncate capitalize text-gray-600">
                        {s.industry.replace(/_/g, " ")}
                      </span>
                      <span
                        className={`shrink-0 font-semibold ${
                          s.shift >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {s.shift >= 0 ? "+" : ""}
                        {(s.shift * 100).toFixed(0)}pp
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Shared donors */}
        {comparison.shared_donors.length > 0 ? (
          <section className="mt-8 rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Shared Donors ({comparison.shared_donors.length})
              </h2>
              <p className="mt-0.5 text-xs text-gray-400">
                Donors who have contributed to all representatives being compared
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                    <th className="px-6 py-3 text-left font-medium">Donor</th>
                    <th className="px-6 py-3 text-left font-medium">Industry</th>
                    {comparison.reps.map((rep) => (
                      <th key={rep.id} className="px-6 py-3 text-right font-medium">
                        {rep.full_name.split(" ").pop()}
                      </th>
                    ))}
                    <th className="px-6 py-3 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {comparison.shared_donors.map((d) => {
                    const total = Object.values(d.amounts).reduce((a, b) => a + b, 0);
                    return (
                      <tr key={d.donor_id} className="hover:bg-gray-50">
                        <td className="px-6 py-3">
                          <Link
                            href={`/donor/${d.donor_id}`}
                            className="font-medium text-blue-600 hover:underline"
                          >
                            {d.donor_name}
                          </Link>
                        </td>
                        <td className="px-6 py-3 text-xs capitalize text-gray-500">
                          {d.industry ? d.industry.replace(/_/g, " ") : "—"}
                        </td>
                        {comparison.reps.map((rep) => (
                          <td key={rep.id} className="px-6 py-3 text-right text-gray-700">
                            {formatDollars(d.amounts[rep.id] ?? 0)}
                          </td>
                        ))}
                        <td className="px-6 py-3 text-right font-semibold text-gray-900">
                          {formatDollars(total)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ) : (
          <div className="mt-8 rounded-lg border border-dashed border-gray-200 p-8 text-center text-sm text-gray-400">
            No shared donors found between these representatives.
          </div>
        )}

        <p className="mt-6 text-xs text-gray-400">
          Funding data sourced from FEC filings. Correlation ≠ causation.{" "}
          <Link href="/docs/methodology" className="underline">
            See methodology.
          </Link>
        </p>
      </div>
    </main>
  );
}

function SelectionPrompt() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Back</Link>
        <h1 className="mt-4 text-2xl font-bold text-gray-900">Compare Representatives</h1>
        <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-400">
          <p className="font-medium">Navigate to a representative profile and click Compare to start.</p>
          <p className="mt-2 text-sm">
            Or use the URL directly:{" "}
            <code className="rounded bg-gray-100 px-1 py-0.5 text-gray-600">
              /compare?ids=REP001,REP002
            </code>
          </p>
        </div>
      </div>
    </main>
  );
}
