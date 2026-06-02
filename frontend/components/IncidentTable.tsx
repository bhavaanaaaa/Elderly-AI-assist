export default function IncidentTable() {
  const incidents = [
    {
      time: "10:22 AM",
      type: "Wet Floor",
      severity: "High",
    },
    {
      time: "10:25 AM",
      type: "Fall Detected",
      severity: "Critical",
    },
  ];

  return (
    <div className="mt-8 bg-zinc-900 rounded-xl p-6 border border-zinc-800">
      <h2 className="text-2xl font-bold text-cyan-400 mb-4">
        Incident Log
      </h2>

      <table className="w-full">
        <thead>
          <tr className="border-b border-zinc-700">
            <th className="text-left p-2">Time</th>
            <th className="text-left p-2">Event</th>
            <th className="text-left p-2">Severity</th>
          </tr>
        </thead>

        <tbody>
          {incidents.map((item, index) => (
            <tr key={index} className="border-b border-zinc-800">
              <td className="p-2">{item.time}</td>
              <td className="p-2">{item.type}</td>
              <td className="p-2 text-red-400">
                {item.severity}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}