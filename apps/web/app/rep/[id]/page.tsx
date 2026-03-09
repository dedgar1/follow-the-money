interface RepProfilePageProps {
  params: Promise<{ id: string }>;
}

export default async function RepProfilePage({ params }: RepProfilePageProps) {
  const { id } = await params;

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-sm text-gray-400">Representative ID: {id}</p>
        {/* Sprint 5: Full rep profile — funding summary, top donors, correlations */}
        <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-400">
          Representative profile — coming Sprint 5
        </div>
      </div>
    </main>
  );
}
