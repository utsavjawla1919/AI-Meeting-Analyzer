/**
 * components/charts/WeeklyBarChart.jsx — Meetings per week bar chart.
 */
import { Bar } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from "chart.js";
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export function WeeklyBarChart({ data = [] }) {
  const labels   = data.map((d) => `W${d._id?.week ?? "?"}`);
  const counts   = data.map((d) => d.count || 0);

  const chartData = {
    labels,
    datasets: [{
      label: "Meetings",
      data: counts,
      backgroundColor: "rgba(99,102,241,0.7)",
      borderRadius: 6,
      borderSkipped: false,
    }],
  };

  const opts = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.y} meeting${ctx.parsed.y !== 1 ? "s" : ""}` } },
    },
    scales: {
      x: { ticks: { color: "#5a5a78", font: { family: "'DM Sans'", size: 11 } }, grid: { display: false } },
      y: { ticks: { color: "#5a5a78", font: { family: "'DM Sans'", size: 11 }, stepSize: 1 }, grid: { color: "rgba(255,255,255,0.04)" } },
    },
  };

  if (!data.length) return (
    <div className="flex items-center justify-center h-36 text-sm text-[var(--text-3)]">No data yet</div>
  );

  return <Bar data={chartData} options={opts} />;
}

export default WeeklyBarChart;
