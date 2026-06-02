export default function CameraGrid() {
  return (
    <div className="mt-8">
      <h2 className="text-2xl font-bold text-cyan-400 mb-4">
        Multi-Camera View
      </h2>

      <div className="grid grid-cols-2 gap-4">

        <div className="h-64 bg-zinc-900 border border-cyan-500 rounded-xl flex items-center justify-center">
          Camera 1
        </div>

        <div className="h-64 bg-zinc-900 border border-green-500 rounded-xl flex items-center justify-center">
          Camera 2
        </div>

        <div className="h-64 bg-zinc-900 border border-yellow-500 rounded-xl flex items-center justify-center">
          Camera 3
        </div>

        <div className="h-64 bg-zinc-900 border border-purple-500 rounded-xl flex items-center justify-center">
          Camera 4
        </div>

      </div>
    </div>
  );
}