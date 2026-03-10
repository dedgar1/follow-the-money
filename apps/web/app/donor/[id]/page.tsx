interface DonorDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function DonorDetailPage({ params }: DonorDetailPageProps) {
  const { id } = await params;

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-sm text-gray-400">Donor ID: {id}</p>
        {/* Sprint 5: Donor detail — recipients, industries, network */}
        <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-400">
          Donor detail — coming Sprint 5
        </div>
      </div>
    </main>
  );
}
