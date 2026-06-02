import Link from "next/link";

export default function Sidebar() {
  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-800 p-6">

      <h1 className="text-2xl font-bold text-cyan-400">
        Hospital AI
      </h1>

      <nav className="mt-10 space-y-4">

        <Link
          href="/"
          className="block bg-cyan-500/10 border border-cyan-500 p-3 rounded-lg hover:bg-cyan-500/20"
        >
          Dashboard
        </Link>

        <Link
          href="/cameras"
          className="block hover:bg-zinc-900 p-3 rounded-lg"
        >
          Cameras
        </Link>

        <Link
          href="/analytics"
          className="block hover:bg-zinc-900 p-3 rounded-lg"
        >
          Analytics
        </Link>

        <Link
          href="/incidents"
          className="block hover:bg-zinc-900 p-3 rounded-lg"
        >
          Incidents
        </Link>

        <Link
          href="/reports"
          className="block hover:bg-zinc-900 p-3 rounded-lg"
        >
          Reports
        </Link>

        <Link
          href="/settings"
          className="block hover:bg-zinc-900 p-3 rounded-lg"
        >
          Settings
        </Link>

      </nav>

    </aside>
  );
}