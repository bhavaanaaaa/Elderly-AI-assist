export default function AnalyticsPage() {
  return (
    <main className="min-h-screen bg-black text-white p-6">
      <h1 className="text-4xl font-bold text-cyan-400 mb-6">
        Analytics Dashboard
      </h1>

      <div className="grid grid-cols-2 gap-6">

        <div className="bg-zinc-900 border border-cyan-500 rounded-xl p-6 h-80">
          <h2 className="text-xl mb-4">Wet Floor Trends</h2>
          <div className="h-56 flex items-center justify-center text-zinc-500">
            Chart Coming Soon
          </div>
        </div>

        <div className="bg-zinc-900 border border-green-500 rounded-xl p-6 h-80">
          <h2 className="text-xl mb-4">Fall Detection Trends</h2>
          <div className="h-56 flex items-center justify-center text-zinc-500">
            Chart Coming Soon
          </div>
        </div>

      </div>
    </main>
  );
}