/**
 * REST API client for the Follow the Money FastAPI backend.
 * Base URL is configured via NEXT_PUBLIC_API_URL (default: http://localhost:8000).
 */

// API_URL is used by Next.js server components (Node.js process, e.g. http://api:8000 in Docker).
// NEXT_PUBLIC_API_URL is the fallback for local dev without Docker.
const API_BASE =
  process.env.API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// ── Response types (mirror apps/api/rest_router.py Pydantic models) ───────────

export interface RepSummary {
  id: string;
  full_name: string;
  party: string;
  chamber: string;
  state: string;
  district: string | null;
  bioguide_id: string | null;
}

export interface IndustrySummary {
  industry: string;
  total_cents: number;
}

export interface TopDonorSummary {
  donor_id: string;
  donor_name: string;
  total_cents: number;
  donor_type: string;
}

export interface RepProfile extends RepSummary {
  total_raised_cents: number;
  small_donor_cents: number;
  foreign_connected_cents: number;
  top_industries: IndustrySummary[];
  top_donors: TopDonorSummary[];
}

export interface PlatformStats {
  total_reps: number;
  total_donors: number;
  total_raised_cents: number;
  total_correlations: number;
}

export interface TickerItem {
  contributor_name: string;
  amount_cents: number;
  committee_id: string;
  contribution_date: string | null;
}

export interface DonorProfile {
  id: string;
  name: string;
  donor_type: string;
  industry: string | null;
  state: string | null;
  total_given_cents: number;
}

export interface DonorRecipient {
  rep_id: string;
  rep_name: string;
  party: string;
  chamber: string;
  state: string;
  total_cents: number;
}

export interface NetworkNode {
  id: string;
  type: "rep" | "donor";
  label: string;
  party?: string;
  chamber?: string;
  state?: string;
  donor_type?: string;
  is_center?: boolean;
}

export interface NetworkEdge {
  source: string;
  target: string;
  total_cents: number;
  cycles: number[];
}

export interface NetworkGraph {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}

export interface VoteRecord {
  vote_id: string;
  bill_id: string;
  bill_title: string;
  industries: string[];       // e.g. ["energy_natural_resources"]
  nlp_confidence: number;
  position: string;           // "yes" | "no" | "abstain" | "not_voting"
  voted_at: string;           // "YYYY-MM-DD"
  chamber: string;            // "house" | "senate"
}

export interface AlignmentScore {
  id: string;
  industry: string;
  score: number;
  confidence: "low" | "medium" | "high";
  evidence_count: number;
  before_score: number;
  after_score: number;
  shift: number;             // positive = more aligned after donation
  p_value: number;
  methodology_url: string;
  computed_at: string | null;
}

export interface ComparisonRepProfile extends RepSummary {
  total_raised_cents: number;
  top_industries: IndustrySummary[];
  top_donors: TopDonorSummary[];
  alignment_scores: AlignmentScore[];
}

export interface SharedDonor {
  donor_id: string;
  donor_name: string;
  donor_type: string;
  industry: string | null;
  amounts: Record<string, number>; // rep_id → cents
}

export interface ComparisonResponse {
  rep_ids: string[];
  reps: ComparisonRepProfile[];
  shared_donors: SharedDonor[];
}

export interface SearchResult {
  type: "rep" | "donor";
  id: string;
  name: string;
  party: string | null;
  chamber: string | null;
  state: string | null;
  donor_type: string | null;
}

// ── Fetch wrapper ──────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/v1${path}`, {
    // No cache in development so data changes (seeds, resets) appear immediately.
    // In production, ISR revalidates every 5 minutes.
    next: process.env.NODE_ENV === "development"
      ? { revalidate: 0 }
      : { revalidate: 300 },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

// ── API methods ────────────────────────────────────────────────────────────────

export const api = {
  listRepresentatives(params?: { state?: string; chamber?: string; party?: string }) {
    const qs = new URLSearchParams();
    if (params?.state) qs.set("state", params.state);
    if (params?.chamber) qs.set("chamber", params.chamber);
    if (params?.party) qs.set("party", params.party);
    const q = qs.toString();
    return apiFetch<RepSummary[]>(`/representatives${q ? `?${q}` : ""}`);
  },

  getRepresentative(id: string) {
    return apiFetch<RepProfile>(`/representatives/${id}`);
  },

  getDonor(id: string) {
    return apiFetch<DonorProfile>(`/donors/${id}`);
  },

  getDonorRecipients(id: string) {
    return apiFetch<DonorRecipient[]>(`/donors/${id}/recipients`);
  },

  search(q: string) {
    return apiFetch<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`);
  },

  getRepNetwork(id: string, limit = 15) {
    return apiFetch<NetworkGraph>(`/representatives/${id}/network?limit=${limit}`);
  },

  getDonorNetwork(id: string, limit = 15) {
    return apiFetch<NetworkGraph>(`/donors/${id}/network?limit=${limit}`);
  },

  getRepVotes(id: string, limit = 50) {
    return apiFetch<VoteRecord[]>(`/representatives/${id}/votes?limit=${limit}`);
  },

  getRepCorrelations(id: string) {
    return apiFetch<AlignmentScore[]>(`/representatives/${id}/correlations`);
  },

  compare(ids: string[]) {
    return apiFetch<ComparisonResponse>(`/compare?ids=${ids.map(encodeURIComponent).join(",")}`);
  },

  getZipReps(zipcode: string) {
    return apiFetch<RepSummary[]>(`/zip/${zipcode}`);
  },

  getStats() {
    return apiFetch<PlatformStats>("/stats");
  },

  getTicker(limit = 20) {
    return apiFetch<TickerItem[]>(`/ticker?limit=${limit}`);
  },
};

// ── Formatting helpers ─────────────────────────────────────────────────────────

/** Returns the direct download URL for a rep's CSV export (browser-accessible). */
export function exportCsvUrl(repId: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base}/v1/export/${repId}.csv`;
}

/** Returns the direct download URL for a rep's JSON export (browser-accessible). */
export function exportJsonUrl(repId: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base}/v1/export/${repId}.json`;
}

export function formatDollars(cents: number): string {
  const dollars = cents / 100;
  if (dollars >= 1_000_000) return `$${(dollars / 1_000_000).toFixed(1)}M`;
  if (dollars >= 1_000) return `$${(dollars / 1_000).toFixed(0)}K`;
  return `$${dollars.toFixed(0)}`;
}

export const PARTY_LABEL: Record<string, string> = {
  D: "Democrat",
  R: "Republican",
  I: "Independent",
  O: "Other",
};

export const CHAMBER_LABEL: Record<string, string> = {
  house: "House",
  senate: "Senate",
};
