import { notFound } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL } from "@/lib/api/client";
import { PartyBadge } from "@/components/shared/PartyBadge";
import { DonutChart } from "@/components/visualizations/DonutChart";
import { TopDonorsBar } from "@/components/visualizations/TopDonorsBar";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function RepProfilePage({ params }: Props) {
  const { id } = await params;

  let rep;
  try {
    rep = await api.getRepresentative(id);
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    if (status === 404) notFound();
    // API down — show empty state rather than crash
    rep = null;
  }

  if (!rep) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-4xl px-6 py-12">
          <Link href="/" className="text-sm text-blue-600 hover:underline">← Back</Link>
          <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-12 text-center text-gray-400">
            Representative not found or API unavailable.
          </div>
        </div>
      </main>
    );
  }

  const partyBorder = rep.party === "D"
    ? "border-l-[var(--color-democrat)]"
    : rep.party === "R"
      ? "border-l-[var(--color-republican)]"
      : "border-l-[var(--color-independent)]";

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* Breadcrumb */}
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← All representatives
        </Link>

        {/* Profile header */}
        <div className={`mt-4 rounded-lg border border-gray-200 border-l-4 ${partyBorder} bg-white p-6 shadow-sm`}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{rep.full_name}</h1>
              <p className="mt-1 text-gray-500">
                {CHAMBER_LABEL[rep.chamber] ?? rep.chamber} ·{" "}
                {rep.state}{rep.district ? ` · ${rep.district}` : ""}
                {rep.bioguide_id && (
                  <span className="ml-2 text-xs text-gray-400">({rep.bioguide_id})</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <PartyBadge party={rep.party} />
              <span className="text-sm font-semibold text-gray-700">
                Total raised: {formatDollars(rep.total_raised_cents)}
              </span>
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          {/* Donut — top industries */}
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Top Industries
            </h2>
            <DonutChart data={rep.top_industries} />
          </section>

          {/* Horizontal bar — top donors */}
          <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Top Donors
            </h2>
            <TopDonorsBar data={rep.top_donors} />
            {rep.top_donors.length > 0 && (
              <ul className="mt-4 space-y-1 text-xs text-gray-500">
                {rep.top_donors.map((d) => (
                  <li key={d.donor_id} className="flex items-center gap-2">
                    <Link
                      href={`/donor/${d.donor_id}`}
                      className="truncate font-medium text-blue-600 hover:underline"
                    >
                      {d.donor_name}
                    </Link>
                    <span className="ml-auto shrink-0">{formatDollars(d.total_cents)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {/* Coming soon placeholders */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-dashed border-gray-200 p-6 text-center text-sm text-gray-400">
            Voting record — Sprint 7
          </div>
          <div className="rounded-lg border border-dashed border-gray-200 p-6 text-center text-sm text-gray-400">
            Donor alignment correlations — Sprint 8
          </div>
        </div>

        {/* Disclaimer */}
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
