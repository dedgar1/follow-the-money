import { notFound } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, CHAMBER_LABEL, exportCsvUrl } from "@/lib/api/client";
import type { AlignmentScore, VoteRecord } from "@/lib/api/client";
import { PartyBadge } from "@/components/shared/PartyBadge";
import { DonutChart } from "@/components/visualizations/DonutChart";
import { TopDonorsBar } from "@/components/visualizations/TopDonorsBar";
import { NetworkGraph } from "@/components/visualizations/NetworkGraph";
import { AlignmentHeatmap } from "@/components/correlation/AlignmentHeatmap";
import { CorrelationTimeline } from "@/components/correlation/CorrelationTimeline";

interface Props {
  params: Promise<{ id: string }>;
}

function VoteBadge({ position }: { position: string }) {
  const styles: Record<string, string> = {
    yes:        "bg-green-100 text-green-700",
    no:         "bg-red-100 text-red-700",
    abstain:    "bg-yellow-100 text-yellow-700",
    not_voting: "bg-gray-100 text-gray-500",
  };
  const labels: Record<string, string> = {
    yes: "Yes", no: "No", abstain: "Abstain", not_voting: "Not Voting",
  };
  const cls = styles[position] ?? "bg-gray-100 text-gray-500";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {labels[position] ?? position}
    </span>
  );
}

export default async function RepProfilePage({ params }: Props) {
  const { id } = await params;

  let rep: Awaited<ReturnType<typeof api.getRepresentative>> | null;
  let network: Awaited<ReturnType<typeof api.getRepNetwork>>;
  let votes: VoteRecord[];
  let correlations: AlignmentScore[];

  try {
    [rep, network, votes, correlations] = await Promise.all([
      api.getRepresentative(id),
      api.getRepNetwork(id).catch(() => ({ nodes: [], edges: [] })),
      api.getRepVotes(id).catch(() => []),
      api.getRepCorrelations(id).catch(() => []),
    ]);
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    if (status === 404) notFound();
    rep = null;
    network = { nodes: [], edges: [] };
    votes = [];
    correlations = [];
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
            <div className="flex flex-wrap items-center gap-3">
              <PartyBadge party={rep.party} />
              <span className="text-sm font-semibold text-gray-700">
                Total raised: {formatDollars(rep.total_raised_cents)}
              </span>
              <Link
                href={`/compare?ids=${rep.id}`}
                className="rounded-md border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                Compare
              </Link>
              <a
                href={exportCsvUrl(rep.id)}
                download
                className="rounded-md border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                Export CSV
              </a>
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

        {/* Funding network */}
        <section className="mt-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Funding Network
          </h2>
          <p className="mb-4 text-xs text-gray-400">
            Donors (◆) who fund this rep and other reps funded by those same donors
          </p>
          <NetworkGraph nodes={network.nodes} edges={network.edges} />
        </section>

        {/* Voting record */}
        <section className="mt-6 rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Voting Record ({votes.length})
            </h2>
          </div>

          {votes.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-gray-400">
              No vote data available — run the ingest pipeline to populate.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                  <th className="px-6 py-3 text-left font-medium">Bill</th>
                  <th className="px-6 py-3 text-left font-medium">Industry</th>
                  <th className="px-6 py-3 text-center font-medium">Vote</th>
                  <th className="px-6 py-3 text-right font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {votes.map((v) => (
                  <tr key={v.vote_id} className="hover:bg-gray-50">
                    <td className="px-6 py-3 max-w-xs">
                      <span className="font-medium text-gray-800">{v.bill_title}</span>
                      {v.bill_id && (
                        <span className="ml-2 text-xs text-gray-400 uppercase">{v.bill_id}</span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      {v.industries.length > 0 ? (
                        <span className="inline-block rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 capitalize">
                          {v.industries[0].replace(/_/g, " ")}
                        </span>
                      ) : (
                        <span className="text-gray-300 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <VoteBadge position={v.position} />
                    </td>
                    <td className="px-6 py-3 text-right text-gray-500">{v.voted_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Donor-industry alignment correlations */}
        <section className="mt-6 rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Donor-Industry Alignment ({correlations.length})
            </h2>
            <p className="mt-0.5 text-xs text-gray-400">
              Voting alignment before and after significant donations. Correlation ≠ causation.{" "}
              <Link href="/docs/methodology" className="underline hover:text-gray-600">
                Methodology
              </Link>
            </p>
          </div>

          <div className="p-6">
            <AlignmentHeatmap scores={correlations} />
          </div>

          {correlations.length > 0 && (
            <div className="border-t border-gray-100 px-6 pb-6">
              <p className="mb-4 mt-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Before / After Detail
              </p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {correlations.slice(0, 6).map((s) => (
                  <CorrelationTimeline key={s.id} score={s} />
                ))}
              </div>
            </div>
          )}
        </section>

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
