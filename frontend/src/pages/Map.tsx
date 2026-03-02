import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDimensions } from "../api/client";
import type { DimensionCard, DimensionOverview } from "../types/api";

const DIMENSION_LABELS: Record<string, string> = {
  compute_and_computational_paradigms: "Compute",
  capital_flows_and_business_models: "Capital",
  energy_resources_and_physical_constraints: "Energy",
  technology_adoption_and_industrial_diffusion: "Tech Adoption",
  governance_regulation_and_societal_response: "Governance",
};

const BORDER_COLORS: Record<string, string> = {
  compute_and_computational_paradigms: "border-violet-400",
  capital_flows_and_business_models: "border-emerald-400",
  energy_resources_and_physical_constraints: "border-orange-400",
  technology_adoption_and_industrial_diffusion: "border-sky-400",
  governance_regulation_and_societal_response: "border-rose-400",
};

const CT_BAR_COLORS: Record<string, string> = {
  reinforcing: "bg-green-400",
  friction: "bg-red-400",
  early_signal: "bg-blue-400",
  neutral: "bg-gray-300",
};

const CT_LABELS: Record<string, string> = {
  reinforcing: "Reinforcing",
  friction: "Friction",
  early_signal: "Early signal",
  neutral: "Neutral",
};

const CT_ORDER = ["reinforcing", "early_signal", "neutral", "friction"];

function ChangeTypeBar({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((s, v) => s + v, 0);
  if (total === 0) return <div className="h-2 bg-gray-100 rounded" />;
  const segments = CT_ORDER
    .filter((k) => (distribution[k] ?? 0) > 0)
    .map((k) => ({ key: k, pct: ((distribution[k] ?? 0) / total) * 100 }));

  return (
    <div>
      <div className="flex h-2 rounded overflow-hidden gap-px">
        {segments.map(({ key, pct }) => (
          <div
            key={key}
            className={CT_BAR_COLORS[key] ?? "bg-gray-300"}
            style={{ width: `${pct}%` }}
          />
        ))}
      </div>
      <div className="flex gap-3 mt-1 flex-wrap">
        {segments.map(({ key, pct }) => (
          <span key={key} className="flex items-center gap-1 text-xs text-gray-500">
            <span className={`inline-block w-2 h-2 rounded-sm ${CT_BAR_COLORS[key] ?? "bg-gray-300"}`} />
            {CT_LABELS[key] ?? key} {Math.round(pct)}%
          </span>
        ))}
      </div>
    </div>
  );
}

function DimensionCardView({ card }: { card: DimensionCard }) {
  const borderColor = BORDER_COLORS[card.dimension] ?? "border-gray-400";
  const label = DIMENSION_LABELS[card.dimension] ?? card.dimension;

  return (
    <div className={`bg-white rounded shadow border-l-4 ${borderColor} px-5 py-4 flex flex-col gap-3`}>
      <div>
        <h2 className="text-lg font-semibold">{label}</h2>
        <p className="text-xs text-gray-500">{card.item_count_30d} signals · 30d</p>
      </div>

      <ChangeTypeBar distribution={card.change_type_distribution} />

      {card.top_entities.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {card.top_entities.slice(0, 3).map((e) => (
            <span key={e} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {e}
            </span>
          ))}
        </div>
      )}

      {card.recent_items.length > 0 && (
        <ul className="space-y-1">
          {card.recent_items.map((item) => (
            <li key={item.id} className="text-sm truncate">
              <Link to={`/items/${item.id}`} className="hover:underline text-gray-700">
                {item.title}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <Link
        to={`/dimensions/${card.dimension}`}
        className="text-xs font-medium text-gray-500 hover:text-gray-800 mt-auto"
      >
        Explore →
      </Link>
    </div>
  );
}

export default function Map() {
  const [overview, setOverview] = useState<DimensionOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDimensions()
      .then(setOverview)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load map");
      });
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!overview) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">The Map</h1>
      <div className="grid md:grid-cols-2 gap-4">
        {overview.dimensions.map((card) => (
          <DimensionCardView key={card.dimension} card={card} />
        ))}
      </div>
    </div>
  );
}
