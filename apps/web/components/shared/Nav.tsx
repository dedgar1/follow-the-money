import Link from "next/link";

export function Nav() {
  return (
    <nav className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xl font-bold text-gray-900">Follow the Money</span>
          </Link>
          <div className="flex items-center gap-6 text-sm text-gray-600">
            <Link href="/?chamber=house" className="hover:text-gray-900">House</Link>
            <Link href="/?chamber=senate" className="hover:text-gray-900">Senate</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
