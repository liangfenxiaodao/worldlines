import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchDimensionDetail } from "../api/client";
import type { DimensionDetail, DimensionDetailItem } from "../types/api";
import ChangeTypeBadge from "../components/ChangeTypeBadge";
import ImportanceBadge from "../components/ImportanceBadge";

const DIMENSION_LABELS: Record<string, string> = {
  compute_and_computational_paradigms: "Compute & Computational Paradigms",
  capital_flows_and_business_models: "Capital Flows & Business Models",
  energy_resources_and_physical_constraints: "Energy, Resources & Physical Constraints",
  technology_adoption_and_industrial_diffusion: "Technology Adoption & Industrial Diffusion",
  governance_regulation_and_societal_response: "Governance, Regulation & Societal Response",
};

const DIMENSION_DESCRIPTIONS: Record<string, string> = {
  compute_and_computational_paradigms:
    "How the world computes — cost, scale, architecture, and bottlenecks.",
  capital_flows_and_business_models:
    "Where capital is deployed and how ROI structures and incentives are shifting.",
  energy_resources_and_physical_constraints:
    "Power, land, water, materials — the non-negotiable real-world limits.",
  technology_adoption_and_industrial_diffusion:
    "The journey from demo to production, from tool to infrastructure.",
  governance_regulation_and_societal_response:
    "Policy, regulation, backlash, and societal alignment or resistance.",
};

const CT_BAR_COLORS: Record<string, string> = {
  reinforcing: "bg-green-400",
  friction: "bg-red-400",
  early_signal: "bg-blue-400",
  neutral: "bg-gray-300",
};

const CT_ORDER = ["reinforcing", "early_signal", "neutral", "friction"];

function ItemCard({ item }: { item: DimensionDetailItem }) {
  return (
    <div className="bg-white rounded shadow px-4 py-3">
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <ChangeTypeBadge changeType={item.change_type} />
        <ImportanceBadge importance={item.importance} />
      </div>
      <Link to={`/items/${item.id}`} className="text-sm font-medium hover:underline">
        {item.title}
      </Link>
      <p className="text-xs text-gray-500 mt-0.5">
        {item.source_name} · {item.timestamp}
      </p>
      <p className="text-sm text-gray-600 mt-1 line-clamp-2">{item.summary}</p>
    </div>
  );
}

export default function DimensionDetailPage() {
  const { dimension } = useParams<{ dimension: string }>();
  const [data, setData] = useState<DimensionDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!dimension) return;
    fetchDimensionDetail(dimension)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load dimension");
      });
  }, [dimension]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  const label = DIMENSION_LABELS[data.dimension] ?? data.dimension;
  const description = DIMENSION_DESCRIPTIONS[data.dimension] ?? "";
  const ctTotal = Object.values(data.change_type_distribution).reduce((s, v) => s + v, 0);

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/" className="text-sm text-gray-500 hover:underline">
        &larr; Map
      </Link>

      <h1 className="text-2xl font-semibold mt-2 mb-1">{label}</h1>
      {description && <p className="text-sm text-gray-500 mb-6">{description}</p>}

      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "7d", count: data.item_count_7d },
          { label: "30d", count: data.item_count_30d },
          { label: "90d", count: data.item_count_90d },
        ].map(({ label, count }) => (
          <div key={label} className="bg-white rounded shadow px-4 py-3 text-center">
            <p className="text-2xl font-semibold">{count}</p>
            <p className="text-xs text-gray-500 uppercase tracking-wide">{label} signals</p>
          </div>
        ))}
      </div>

      {ctTotal > 0 && (
        <div className="bg-white rounded shadow px-4 py-4 mb-6">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Signal types</h2>
          <div className="space-y-2">
            {CT_ORDER.filter((k) => (data.change_type_distribution[k] ?? 0) > 0).map((k) => {
              const count = data.change_type_distribution[k] ?? 0;
              const pct = ctTotal ? (count / ctTotal) * 100 : 0;
              return (
                <div key={k} className="flex items-center gap-3">
                  <span className="text-xs text-gray-600 w-24 capitalize">
                    {k.replace(/_/g, " ")}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded h-2">
                    <div
                      className={`h-2 rounded ${CT_BAR_COLORS[k] ?? "bg-gray-400"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 w-8 text-right">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {data.top_entities.length > 0 && (
        <div className="bg-white rounded shadow px-4 py-4 mb-6">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Key entities</h2>
          <div className="flex flex-wrap gap-2">
            {data.top_entities.map((e) => (
              <span key={e} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">
                {e}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.recent_items.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-700 mb-3">Recent signals</h2>
          <div className="flex flex-col gap-3">
            {data.recent_items.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
