export default function IncidentsPage() {
  const incidents = [
    {
      time: "10:22 AM",
      event: "Wet Floor",
      severity: "High",
    },
    {
      time: "10:30 AM",
      event: "Fall Detected",
      severity: "Critical",
    },
  ];

  return (
    <main className="min-h-screen bg-black text-white p-6">
      <h1 className="text-4xl font-bold text-cyan-400 mb-6">
        Incident Management
      </h1>

      <div className="bg-zinc-900 rounded-xl border border-zinc-700 p-6">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-left p-3">Time</th>
              <th className="text-left p-3">Event</th>
              <th className="text-left p-3">Severity</th>
            </tr>
          </thead>

          <tbody>
            {incidents.map((item, index) => (
              <tr key={index}>
                <td className="p-3">{item.time}</td>
                <td className="p-3">{item.event}</td>
                <td className="p-3 text-red-400">
                  {item.severity}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}