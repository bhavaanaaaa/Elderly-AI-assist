export default function ReportsPage() {
  return (
    <main className="min-h-screen bg-black text-white p-6">
      <h1 className="text-4xl font-bold text-cyan-400 mb-6">
        Reports Center
      </h1>

      <div className="grid grid-cols-3 gap-6">

        <div className="bg-zinc-900 p-6 rounded-xl border border-cyan-500">
          <h2 className="text-xl mb-4">
            Daily Report
          </h2>

          <button className="bg-cyan-500 text-black px-4 py-2 rounded">
            Download PDF
          </button>
        </div>

        <div className="bg-zinc-900 p-6 rounded-xl border border-green-500">
          <h2 className="text-xl mb-4">
            Weekly Report
          </h2>

          <button className="bg-green-500 text-black px-4 py-2 rounded">
            Download CSV
          </button>
        </div>

        <div className="bg-zinc-900 p-6 rounded-xl border border-purple-500">
          <h2 className="text-xl mb-4">
            AI Summary
          </h2>

          <button className="bg-purple-500 text-black px-4 py-2 rounded">
            Generate
          </button>
        </div>

      </div>
    </main>
  );
}