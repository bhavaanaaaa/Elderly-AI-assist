type StatsProps = {
  stats?: {
    wet_floor_events: number;
    persons_detected: number;
    fall_events: number;
    unique_persons: number;
  };
};

export default function StatsPanel({ stats }: StatsProps) {
  return (
    <div className="grid grid-cols-4 gap-4 mt-10">

      <div className="bg-zinc-900 p-6 rounded-xl border border-cyan-500">
        <h2 className="text-xl">Wet Floor Alerts</h2>
        <p className="text-3xl mt-4 font-bold text-red-400">
          {stats?.wet_floor_events ?? 0}
        </p>
      </div>

      <div className="bg-zinc-900 p-6 rounded-xl border border-green-500">
        <h2 className="text-xl">People Detected</h2>
        <p className="text-3xl mt-4 font-bold text-green-400">
          {stats?.persons_detected ?? 0}
        </p>
      </div>

      <div className="bg-zinc-900 p-6 rounded-xl border border-yellow-500">
        <h2 className="text-xl">Falls Detected</h2>
        <p className="text-3xl mt-4 font-bold text-yellow-400">
          {stats?.fall_events ?? 0}
        </p>
      </div>

      <div className="bg-zinc-900 p-6 rounded-xl border border-purple-500">
        <h2 className="text-xl">Unique Persons</h2>
        <p className="text-3xl mt-4 font-bold text-purple-400">
          {stats?.unique_persons ?? 0}
        </p>
      </div>

    </div>
  );
}