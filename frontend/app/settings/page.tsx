export default function SettingsPage() {
  return (
    <main className="min-h-screen bg-black text-white p-6">

      <h1 className="text-4xl font-bold text-cyan-400 mb-6">
        System Settings
      </h1>

      <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-700">

        <div className="mb-6">
          <label className="block mb-2">
            Alert Email
          </label>

          <input
            type="email"
            placeholder="admin@hospital.com"
            className="w-full p-3 rounded bg-black border border-zinc-700"
          />
        </div>

        <div className="mb-6">
          <label className="block mb-2">
            Twilio Number
          </label>

          <input
            type="text"
            placeholder="+91XXXXXXXXXX"
            className="w-full p-3 rounded bg-black border border-zinc-700"
          />
        </div>

        <button className="bg-cyan-500 text-black px-6 py-3 rounded">
          Save Settings
        </button>

      </div>

    </main>
  );
}