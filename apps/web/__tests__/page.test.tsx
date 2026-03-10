import { render, screen } from "@testing-library/react";
import { vi, beforeEach } from "vitest";

// Mock the API client so tests don't need a running backend
vi.mock("@/lib/api/client", () => ({
  api: {
    listRepresentatives: vi.fn().mockResolvedValue([]),
    search: vi.fn().mockResolvedValue([]),
    getRepresentative: vi.fn().mockResolvedValue(null),
    getDonor: vi.fn().mockResolvedValue(null),
    getDonorRecipients: vi.fn().mockResolvedValue([]),
  },
  formatDollars: (cents: number) => `$${(cents / 100).toFixed(0)}`,
  PARTY_LABEL: { D: "Democrat", R: "Republican", I: "Independent", O: "Other" },
  CHAMBER_LABEL: { house: "House", senate: "Senate" },
}));

// Mock Next.js navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders the headline", async () => {
    const element = await HomePage({ searchParams: Promise.resolve({}) });
    render(element);
    expect(screen.getByText("Follow the Money")).toBeInTheDocument();
  });

  it("renders the description", async () => {
    const element = await HomePage({ searchParams: Promise.resolve({}) });
    render(element);
    expect(screen.getByText(/Find your representatives/i)).toBeInTheDocument();
  });

  it("shows empty state when no reps are loaded", async () => {
    const element = await HomePage({ searchParams: Promise.resolve({}) });
    render(element);
    expect(screen.getByText(/No representatives loaded yet/i)).toBeInTheDocument();
  });
});

import { PartyBadge } from "@/components/shared/PartyBadge";

describe("PartyBadge", () => {
  it("renders Democrat label", () => {
    render(<PartyBadge party="D" />);
    expect(screen.getByText("Democrat")).toBeInTheDocument();
  });

  it("renders Republican label", () => {
    render(<PartyBadge party="R" />);
    expect(screen.getByText("Republican")).toBeInTheDocument();
  });
});
