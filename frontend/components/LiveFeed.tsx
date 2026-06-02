export default function LiveFeed() {
  return (
    <div className="mt-10 bg-zinc-900 border border-zinc-800 rounded-2xl p-6">

      <h2 className="text-2xl font-semibold mb-4 text-cyan-400">
        Live AI Monitoring
      </h2>

      <div className="h-[400px] rounded-xl bg-black border border-cyan-500 flex items-center justify-center">
        <p className="text-zinc-500 text-xl">
          Live Camera Feed Here
        </p>
      </div>

    </div>
  );
}