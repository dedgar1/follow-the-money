import { notFound } from "next/navigation";
import Link from "next/link";
import { api, formatDollars, PARTY_LABEL, CHAMBER_LABEL } from "@/lib/api/client";
import { PartyBadge } from "@/components/shared/PartyBadge";
import { NetworkGraph } from "@/components/visualizations/NetworkGraph";

interface Props {
  params: Promise<{ id: string }>;
}

const DONOR_TYPE_LABEL: Record<string, string> = {
  individual: "Individual",
  pac: "PAC",
  corporation: "Corporation",
  union: "Union",
  other: "Other",
};

export default async function DonorDetailPage({ params }: Props) {
  const { id } = await params;

  let donor: Awaited<ReturnType<typeof api.getDonor>> | null;
  let recipients: Awaited<ReturnType<typeof api.getDonorRecipients>>;
  let network: Awaited<ReturnType<typeof api.getDonorNetwork>>;

  try {
    [donor, recipients, network] = await Promise.all([
      api.getDonor(id),
      api.getDonorRecipients(id),
      api.getDonorNetwork(id).catch(() => ({ nodes: [], edges: [] })),
    ]);
  } catch (err: unknown) {
    const status = (err as { status?: number })?.status;
    if (status === 404) notFound();
    donor = null;
    recipients = [];
    network = { nodes: [], edges: [] };
  }

  if (!donor) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-4xl px-6 py-12">
          <Link href="/" className="text-sm text-blue-600 hover:underline">← Back</Link>
          <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-12 text-center text-gray-400">
            Donor not found or API unavailable.
          </div>
        </div>
      </main>
    );
  }

  const democrats = recipients.filter((r) => r.party === "D");
  const republicans = recipients.filter((r) => r.party === "R");
  const demTotal = democrats.reduce((s, r) => s + r.total_cents, 0);
  const repTotal = republicans.reduce((s, r) => s + r.total_cents, 0);
  const grandTotal = recipients.reduce((s, r) => s + r.total_cents, 0);

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-4xl px-6 py-8">
        {/* Breadcrumb */}
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Search
        </Link>

        {/* Donor header */}
        <div className="mt-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{donor.name}</h1>
              <p className="mt-1 text-gray-500">
                {DONOR_TYPE_LABEL[donor.donor_type] ?? donor.donor_type}
                {donor.industry && ` · ${donor.industry}`}
                {donor.state && ` · ${donor.state}`}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Total given</p>
              <p className="text-xl font-bold text-gray-900">{formatDollars(donor.total_given_cents)}</p>
            </div>
          </div>

          {/* Party split bar */}
          {grandTotal > 0 && (
            <div className="mt-5">
              <p className="mb-1.5 text-xs text-gray-500">Giving by party</p>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-gray-100">
                {demTotal > 0 && (
                  <div
                    className="bg-[var(--color-democrat)] transition-all"
                    style={{ width: `${(demTotal / grandTotal) * 100}%` }}
                  />
                )}
                {repTotal > 0 && (
                  <div
                    className="bg-[var(--color-republican)] transition-all"
                    style={{ width: `${(repTotal / grandTotal) * 100}%` }}
                  />
                )}
              </div>
              <div className="mt-1.5 flex gap-4 text-xs text-gray-500">
                <span>
                  <span className="font-medium text-blue-700">Dem</span>{" "}
                  {formatDollars(demTotal)} ({democrats.length})
                </span>
                <span>
                  <span className="font-medium text-red-700">Rep</span>{" "}
                  {formatDollars(repTotal)} ({republicans.length})
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Recipients table */}
        <section className="mt-6 rounded-lg border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Recipients ({recipients.length})
            </h2>
          </div>

          {recipients.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-gray-400">
              No recipients found for this donor.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                  <th className="px-6 py-3 text-left font-medium">Representative</th>
                  <th className="px-6 py-3 text-left font-medium">Party</th>
                  <th className="px-6 py-3 text-left font-medium">State · Chamber</th>
                  <th className="px-6 py-3 text-right font-medium">Total given</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recipients.map((r) => (
                  <tr key={r.rep_id} className="hover:bg-gray-50">
                    <td className="px-6 py-3">
                      <Link href={`/rep/${r.rep_id}`} className="font-medium text-blue-600 hover:underline">
                        {r.rep_name}
                      </Link>
                    </td>
                    <td className="px-6 py-3">
                      <PartyBadge party={r.party} />
                    </td>
                    <td className="px-6 py-3 text-gray-500">
                      {r.state} · {CHAMBER_LABEL[r.chamber] ?? r.chamber}
                    </td>
                    <td className="px-6 py-3 text-right font-medium text-gray-800">
                      {formatDollars(r.total_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* Funding network */}
        <section className="mt-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Funding Network
          </h2>
          <p className="mb-4 text-xs text-gray-400">
            Reps (●) funded by this donor and other donors (◆) who fund the same reps
          </p>
          <NetworkGraph nodes={network.nodes} edges={network.edges} />
        </section>

        <p className="mt-6 text-xs text-gray-400">
          Funding data sourced from FEC filings. Correlation ≠ causation.
        </p>
      </div>
    </main>
  );
}
