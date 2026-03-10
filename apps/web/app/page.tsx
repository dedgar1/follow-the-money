export default function HomePage() {
  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-4xl px-6 py-24">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">
          Follow the Money
        </h1>
        <p className="mt-4 text-lg text-gray-600">
          Find your representatives. See who funds them. Understand how donations
          shape their votes.
        </p>

        {/* Sprint 5: Replace with ZIP search + map */}
        <div className="mt-12 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-400">
          ZIP code search + district map — coming Sprint 5
        </div>
      </div>
    </main>
  );
}
