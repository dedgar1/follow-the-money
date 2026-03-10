import { Suspense } from "react";
import { SearchBar } from "@/components/shared/SearchBar";
import { RepCard } from "@/components/shared/RepCard";
import { api } from "@/lib/api/client";
import type { RepSummary, SearchResult } from "@/lib/api/client";
import { PARTY_LABEL, CHAMBER_LABEL } from "@/lib/api/client";
import Link from "next/link";

interface Props {
  searchParams: Promise<{ q?: string; state?: string; chamber?: string }>;
}

async function fetchReps(params: { state?: string; chamber?: string }): Promise<RepSummary[]> {
  try {
    return await api.listRepresentatives(params);
  } catch {
    return [];
  }
}

async function fetchSearch(q: string): Promise<SearchResult[]> {
  try {
    return await api.search(q);
  } catch {
    return [];
  }
}

export default async function HomePage({ searchParams }: Props) {
  const { q, state, chamber } = await searchParams;
  const hasSearch = Boolean(q?.trim());

  const [reps, searchResults] = await Promise.all([
    hasSearch ? Promise.resolve([]) : fetchReps({ state, chamber }),
    hasSearch ? fetchSearch(q!) : Promise.resolve([]),
  ]);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Hero */}
      <div className="bg-white border-b border-gray-200">
        <div className="mx-auto max-w-4xl px-6 py-12">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Follow the Money
          </h1>
          <p className="mt-3 text-lg text-gray-600">
            Find your representatives. See who funds them. Understand how donations shape their votes.
          </p>
          <div className="mt-6">
            <Suspense>
              <SearchBar defaultValue={q} />
            </Suspense>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-6 py-8">
        {hasSearch ? (
          <SearchResultsList results={searchResults} query={q!} />
        ) : (
          <RepList reps={reps} state={state} chamber={chamber} />
        )}
      </div>
    </main>
  );
}

function SearchResultsList({ results, query }: { results: SearchResult[]; query: string }) {
  return (
    <div>
      <h2 className="mb-4 text-sm font-medium text-gray-500">
        {results.length === 0
          ? `No results for "${query}"`
          : `${results.length} result${results.length !== 1 ? "s" : ""} for "${query}"`}
      </h2>
      {results.length > 0 && (
        <ul className="space-y-2">
          {results.map((r) => (
            <li key={`${r.type}-${r.id}`}>
              {r.type === "rep" ? (
                <Link
                  href={`/rep/${r.id}`}
                  className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm hover:shadow-md"
                >
                  <div>
                    <span className="font-medium text-gray-900">{r.name}</span>
                    {r.state && (
                      <span className="ml-2 text-sm text-gray-500">
                        {r.state} · {r.chamber ? CHAMBER_LABEL[r.chamber] : ""} ·{" "}
                        {r.party ? PARTY_LABEL[r.party] : ""}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">Representative →</span>
                </Link>
              ) : (
                <Link
                  href={`/donor/${r.id}`}
                  className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-sm hover:shadow-md"
                >
                  <div>
                    <span className="font-medium text-gray-900">{r.name}</span>
                    {r.state && (
                      <span className="ml-2 text-sm text-gray-500">
                        {r.state} · {r.donor_type}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">Donor →</span>
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RepList({
  reps,
  state,
  chamber,
}: {
  reps: RepSummary[];
  state?: string;
  chamber?: string;
}) {
  const filterLabel = [
    state ? `State: ${state.toUpperCase()}` : null,
    chamber ? `Chamber: ${CHAMBER_LABEL[chamber] ?? chamber}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-500">
          {filterLabel || "All representatives"}
          {reps.length > 0 && ` — ${reps.length} shown`}
        </h2>
        <div className="flex gap-2 text-sm">
          <Link
            href="/?chamber=house"
            className={`rounded px-2 py-1 ${chamber === "house" ? "bg-gray-900 text-white" : "text-gray-600 hover:text-gray-900"}`}
          >
            House
          </Link>
          <Link
            href="/?chamber=senate"
            className={`rounded px-2 py-1 ${chamber === "senate" ? "bg-gray-900 text-white" : "text-gray-600 hover:text-gray-900"}`}
          >
            Senate
          </Link>
          {(chamber || state) && (
            <Link href="/" className="rounded px-2 py-1 text-gray-400 hover:text-gray-900">
              Clear
            </Link>
          )}
        </div>
      </div>

      {reps.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 py-16 text-center text-gray-400">
          <p className="text-sm">No representatives loaded yet.</p>
          <p className="mt-1 text-xs">Run the data pipeline to populate representative data.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {reps.map((rep) => (
            <RepCard key={rep.id} rep={rep} />
          ))}
        </div>
      )}
    </div>
  );
}
