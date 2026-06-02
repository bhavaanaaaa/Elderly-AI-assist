export async function getStats() {
  try {
    const response = await fetch(
      "http://localhost:8000/api/stats",
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Stats API error:", error);

    return {
      total_detections: 0,
      danger_events: 0,
      fall_events: 0,
      wet_floor_events: 0,
      ppe_violations: 0,
      crowd_alerts: 0,
      persons_detected: 0,
      alerts_sent: 0,
      unique_persons: 0,
    };
  }
}