/**
 * components/charts/SentimentDoughnutChart.jsx
 */
import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";
ChartJS.register(ArcElement, Tooltip, Legend);

export default function SentimentDoughnutChart({ data, labels, colors }) {
  const values = labels.map((l) => {
    const key = l.toLowerCase();
    return typeof data[key] === "number" ? Math.round(data[key] * 100) : (data[key] || 0);
  });

  const chartData = {
    labels,
    datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }],
  };

  const opts = {
    responsive: true,
    cutout: "68%",
    plugins: {
      legend: { position: "bottom", labels: { color: "#9898b0", font: { family: "'DM Sans'" }, padding: 16, boxWidth: 12, borderRadius: 4 } },
      tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed}%` } },
    },
  };

  const total = values.reduce((a, b) => a + b, 0);

  return (
    <div className="relative">
      <Doughnut data={chartData} options={opts} />
      {total > 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ top: "-10%" }}>
          <div className="text-center">
            <p className="text-lg font-bold text-[var(--text)]">{values[0]}%</p>
            <p className="text-xs text-[var(--text-3)]">{labels[0]}</p>
          </div>
        </div>
      )}
    </div>
  );
}
