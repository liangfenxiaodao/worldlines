import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { fetchTickerExposures } from "../api/client";
import type { TickerExposureResponse } from "../types/api";
import DimensionBadge from "../components/DimensionBadge";
import ImportanceBadge from "../components/ImportanceBadge";
import Pagination from "../components/Pagination";

const EXPOSURE_TYPE_COLORS: Record<string, string> = {
  direct: "bg-indigo-100 text-indigo-800",
  indirect: "bg-cyan-100 text-cyan-800",
  contextual: "bg-slate-100 text-slate-700",
};

const STRENGTH_COLORS: Record<string, string> = {
  core: "bg-red-100 text-red-800",
  material: "bg-amber-100 text-amber-800",
  peripheral: "bg-gray-100 text-gray-600",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-gray-100 text-gray-500",
};

const ROLE_LABELS: Record<string, string> = {
  infrastructure_operator: "Infrastructure",
  upstream_supplier: "Supplier",
  downstream_adopter: "Adopter",
  platform_intermediary: "Platform",
  regulated_entity: "Regulated",
  capital_allocator: "Capital",
  other: "Other",
};

export default function TickerDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");

  const [data, setData] = useState<TickerExposureResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ticker) return;
    setData(null);
    setError("");
    fetchTickerExposures(ticker, { page })
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load exposures");
      });
  }, [ticker, page]);

  function goPage(p: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="mb-5">
        <Link to="/exposures" className="text-sm text-gray-500 hover:underline">
          ← Exposures
        </Link>
      </div>

      <div className="flex items-baseline gap-3 mb-1">
        <h1 className="font-mono text-3xl font-bold">{data.ticker}</h1>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        {data.total} article{data.total !== 1 ? "s" : ""}
      </p>

      {data.entries.length === 0 ? (
        <p className="text-gray-500">No exposure records found for {data.ticker}.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.entries.map((entry) => (
            <div
              key={`${entry.item_id}-${entry.analysis_id}`}
              className="bg-white rounded shadow px-5 py-4"
            >
              <div className="flex items-start justify-between gap-2 mb-1 flex-wrap">
                <Link
                  to={`/items/${entry.item_id}`}
                  className="font-semibold text-sm hover:underline"
                >
                  {entry.item_title}
                </Link>
                <ImportanceBadge importance={entry.importance} />
              </div>

              <p className="text-xs text-gray-400 mb-3">
                {entry.source_name} · {entry.item_timestamp}
              </p>

              <div className="flex items-center gap-2 flex-wrap mb-3">
                <span
                  className={`text-xs px-2 py-0.5 rounded font-medium ${EXPOSURE_TYPE_COLORS[entry.exposure_type] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {entry.exposure_type}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-medium ${STRENGTH_COLORS[entry.exposure_strength] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {entry.exposure_strength}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-medium ${CONFIDENCE_COLORS[entry.confidence] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {entry.confidence} confidence
                </span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {ROLE_LABELS[entry.business_role] ?? entry.business_role}
                </span>
              </div>

              <p className="text-sm text-gray-700 mb-3">{entry.rationale}</p>

              <div className="flex gap-1 flex-wrap mb-3">
                {entry.dimensions_implicated.map((d) => (
                  <DimensionBadge key={d} dimension={d} />
                ))}
              </div>

              <p className="text-xs text-gray-400">Mapped {entry.mapped_at}</p>
            </div>
          ))}
        </div>
      )}

      <Pagination page={data.page} pages={data.pages} onPage={goPage} />
    </div>
  );
}
