/**
 * components/charts/SpeakerBarChart.jsx — Per-speaker sentiment bar chart.
 */
import { Bar } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from "chart.js";
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export default function SpeakerBarChart({ data = {} }) {
  const speakers = Object.keys(data);
  if (!speakers.length) return <div className="text-sm text-[var(--text-3)] text-center py-8">No speaker data</div>;

  const posData = speakers.map((s) => Math.round((data[s].positive || 0) * 100));
  const negData = speakers.map((s) => Math.round((data[s].negative || 0) * 100));
  const neuData = speakers.map((s) => Math.round((data[s].neutral  || 0) * 100));

  const chartData = {
    labels: speakers,
    datasets: [
      { label: "Positive", data: posData, backgroundColor: "rgba(16,185,129,0.75)",  borderRadius: 4 },
      { label: "Negative", data: negData, backgroundColor: "rgba(239,68,68,0.75)",   borderRadius: 4 },
      { label: "Neutral",  data: neuData, backgroundColor: "rgba(148,163,184,0.45)", borderRadius: 4 },
    ],
  };

  const opts = {
    responsive: true,
    scales: {
      x: { stacked: true, ticks: { color: "#9898b0", font: { family: "'DM Sans'" } }, grid: { display: false } },
      y: { stacked: true, max: 100, ticks: { color: "#9898b0", font: { family: "'DM Sans'" }, callback: (v) => `${v}%` }, grid: { color: "rgba(255,255,255,0.04)" } },
    },
    plugins: {
      legend: { position: "top", labels: { color: "#9898b0", font: { family: "'DM Sans'" }, boxWidth: 12, padding: 16 } },
      tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}%` } },
    },
  };

  return <Bar data={chartData} options={opts} />;
}
