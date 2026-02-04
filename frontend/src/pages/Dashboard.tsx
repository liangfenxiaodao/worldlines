import { useEffect, useState } from "react";
import { fetchStats } from "../api/client";
import type { StatsResponse } from "../types/api";
import { dimensionLabel } from "../components/DimensionBadge";

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchStats().then(setStats).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : "Failed to load stats");
    });
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!stats) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <Card label="Items" value={stats.total_items} />
        <Card label="Analyses" value={stats.total_analyses} />
        <Card label="Digests" value={stats.total_digests} />
        <Card label="Latest digest" value={stats.latest_digest_date ?? "---"} />
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <Breakdown title="Dimensions" data={stats.dimension_breakdown} labelFn={dimensionLabel} />
        <Breakdown title="Change type" data={stats.change_type_distribution} />
        <Breakdown title="Importance" data={stats.importance_distribution} />
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded shadow px-4 py-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="text-xl font-semibold mt-1">{value}</p>
    </div>
  );
}

function Breakdown({
  title,
  data,
  labelFn,
}: {
  title: string;
  data: Record<string, number>;
  labelFn?: (k: string) => string;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  const total = entries.reduce((s, [, v]) => s + v, 0);
  return (
    <div className="bg-white rounded shadow px-4 py-3">
      <h3 className="text-sm font-medium text-gray-700 mb-2">{title}</h3>
      <ul className="space-y-1">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between text-sm">
            <span className="text-gray-600">{labelFn ? labelFn(k) : k.replace(/_/g, " ")}</span>
            <span className="font-medium">
              {v} <span className="text-gray-400 text-xs">({total ? Math.round((v / total) * 100) : 0}%)</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
