"use client";

import {
  Chart as ChartJS,
  LinearScale,
  LogarithmicScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type { ComplexityResult } from "@/lib/types";

ChartJS.register(LinearScale, LogarithmicScale, PointElement, LineElement, Tooltip, Legend);

interface ComplexityChartProps {
  result: ComplexityResult | null;
}

const REFERENCE_MODELS: Record<string, (n: number) => number> = {
  "O(1)": () => 1,
  "O(log N)": (n) => Math.log2(Math.max(n, 2)),
  "O(N)": (n) => n,
  "O(N log N)": (n) => n * Math.log2(Math.max(n, 2)),
  "O(N^2)": (n) => n * n,
};

const REFERENCE_COLORS: Record<string, string> = {
  "O(1)": "#9aa2b8",
  "O(log N)": "#5b9ee8",
  "O(N)": "#3fc5b7",
  "O(N log N)": "#8b7cf6",
  "O(N^2)": "#f0648c",
};

function logSpace(min: number, max: number, count: number): number[] {
  const logMin = Math.log10(min);
  const logMax = Math.log10(max);
  const step = (logMax - logMin) / (count - 1);
  return Array.from({ length: count }, (_, i) => Math.pow(10, logMin + i * step));
}

const EXPLANATIONS: Record<string, string> = {
  "O(1)": "Constant time — the operation count doesn't grow with input size. Typical of direct index access or fixed-size work.",
  "O(log N)": "Logarithmic time — the operation count grows very slowly as N increases. Typical of binary search or halving-based algorithms.",
  "O(N)": "Linear time — the operation count grows proportionally with N. Typical of a single pass over the input.",
  "O(N log N)": "Linearithmic time — grows a bit faster than linear. Typical of efficient sorting algorithms (merge sort, quicksort average case).",
  "O(N^2)": "Quadratic time — the operation count grows with the square of N. Typical of nested loops over the same input (e.g. bubble sort).",
  "O(N^3)": "Cubic time — grows with the cube of N. Typical of triple-nested loops, e.g. naive matrix multiplication.",
};

export default function ComplexityChart({ result }: ComplexityChartProps) {
  if (!result || !result.supported) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-paper/40">
        {result?.message ?? "Benchmark results will appear here after you run your code."}
      </div>
    );
  }

  if (result.n_values.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-paper/40">
        {result.error ?? "No benchmark data yet."}
      </div>
    );
  }

  const empiricalPoints = result.n_values.map((n, i) => ({ x: n, y: result.step_counts[i] }));
  const minN = Math.min(...result.n_values);
  const maxN = Math.max(...result.n_values);
  const lastN = result.n_values[result.n_values.length - 1];
  const lastSteps = result.step_counts[result.step_counts.length - 1];
  const referenceXs = logSpace(minN, maxN, 20);

  const referenceDatasets = Object.entries(REFERENCE_MODELS).map(([label, fn]) => {
    const scale = lastSteps / fn(lastN);
    const isEstimated = label === result.estimated_big_o;
    return {
      label,
      data: referenceXs.map((x) => ({ x, y: fn(x) * scale })),
      borderColor: REFERENCE_COLORS[label],
      borderWidth: isEstimated ? 2.5 : 1,
      borderDash: isEstimated ? [] : [4, 4],
      pointRadius: 0,
      tension: 0.1,
    };
  });

  const data = {
    datasets: [
      {
        label: "Measured T(N)",
        data: empiricalPoints,
        borderColor: "#e8a33d",
        backgroundColor: "#e8a33d",
        pointRadius: 5,
        pointBackgroundColor: "#e8a33d",
        showLine: false,
      },
      ...referenceDatasets,
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    parsing: false as const,
    scales: {
      x: {
        type: "logarithmic" as const,
        title: { display: true, text: "Input size N", color: "#4a5068" },
        ticks: { color: "#4a5068" },
        grid: { color: "#242836" },
      },
      y: {
        type: "logarithmic" as const,
        title: { display: true, text: "Operations T(N)", color: "#4a5068" },
        ticks: { color: "#4a5068" },
        grid: { color: "#242836" },
      },
    },
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: { color: "#eef0f5", boxWidth: 12, font: { size: 10 } },
      },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { x: number; y: number } }) =>
            `${ctx.dataset.label}: N=${Math.round(ctx.parsed.x)}, T=${Math.round(ctx.parsed.y)}`,
        },
      },
    },
  };

  const explanation = result.estimated_big_o ? EXPLANATIONS[result.estimated_big_o] : null;

  return (
    <div className="grid h-full w-full grid-cols-1 gap-4 p-4 lg:grid-cols-[1fr_320px]">
      <div className="flex min-h-0 flex-col">
        <div className="flex items-center justify-between pb-2">
          <span className="text-sm text-paper/50">Empirical Big-O benchmark</span>
          <span className="rounded bg-signal/15 px-2.5 py-1 font-mono text-sm font-semibold text-signal">
            Detected Order of Growth: {result.estimated_big_o ?? "unknown"}
          </span>
        </div>
        <div className="min-h-0 flex-1">
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <Line data={data} options={options as any} />
        </div>
        {result.error && (
          <p className="pt-1 text-xs text-node-condition">{result.error}</p>
        )}
      </div>

      <div className="flex flex-col gap-4 overflow-y-auto">
        <section className="rounded-lg border border-ink-700 bg-ink-900 p-3">
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-paper/40">
            What this means
          </h3>
          <p className="text-sm leading-relaxed text-paper/80">
            {explanation ?? "Run more benchmark samples to get a confident classification."}
          </p>
        </section>

        <section className="rounded-lg border border-ink-700 bg-ink-900 p-3">
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-paper/40">
            Raw samples
          </h3>
          <table className="w-full font-mono text-xs">
            <thead>
              <tr className="text-paper/40">
                <th className="pb-1 text-left">N</th>
                <th className="pb-1 text-right">T(N)</th>
              </tr>
            </thead>
            <tbody>
              {result.n_values.map((n, i) => (
                <tr key={n} className="border-t border-ink-700/60">
                  <td className="py-1 text-paper/80">{n}</td>
                  <td className="py-1 text-right text-paper/80">{result.step_counts[i]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
