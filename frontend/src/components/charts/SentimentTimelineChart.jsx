/**
 * components/charts/SentimentTimelineChart.jsx — Smoothed sentiment over time.
 */
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Tooltip, Legend, Filler,
} from "chart.js";
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

export default function SentimentTimelineChart({ data = [] }) {
  if (!data.length) return (
    <div className="flex items-center justify-center h-40 text-sm text-[var(--text-3)]">
      No timeline data available
    </div>
  );

  const labels   = data.map((d) => {
    const m = Math.floor((d.start || 0) / 60);
    const s = Math.floor((d.start || 0) % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  });

  const posData  = data.map((d) => Math.round((d.smoothed_positive ?? d.positive ?? 0) * 100));
  const negData  = data.map((d) => Math.round((d.smoothed_negative ?? d.negative ?? 0) * 100));

  const chartData = {
    labels,
    datasets: [
      {
        label: "Positive",
        data: posData,
        borderColor: "#10b981",
        backgroundColor: "rgba(16,185,129,0.08)",
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: "Negative",
        data: negData,
        borderColor: "#ef4444",
        backgroundColor: "rgba(239,68,68,0.08)",
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };

  const opts = {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", labels: { color: "#9898b0", font: { family: "'DM Sans'" }, boxWidth: 12, padding: 16 } },
      tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%` } },
    },
    scales: {
      x: { ticks: { color: "#5a5a78", font: { family: "'DM Sans'", size: 10 }, maxTicksLimit: 8 }, grid: { color: "rgba(255,255,255,0.04)" } },
      y: { min: 0, max: 100, ticks: { color: "#5a5a78", font: { family: "'DM Sans'", size: 10 }, callback: (v) => `${v}%` }, grid: { color: "rgba(255,255,255,0.04)" } },
    },
  };

  return <Line data={chartData} options={opts} />;
}
