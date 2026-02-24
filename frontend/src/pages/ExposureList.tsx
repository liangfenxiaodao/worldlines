import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { fetchExposures } from "../api/client";
import type { ExposureDetail, ExposureListResponse } from "../types/api";
import DimensionBadge from "../components/DimensionBadge";
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

function ExposureRow({ record }: { record: ExposureDetail }) {
  if (record.skipped_reason) {
    return (
      <div className="bg-white rounded shadow px-5 py-4 text-sm text-gray-400 italic">
        No exposures mapped — {record.skipped_reason}
        <span className="block text-xs mt-1 not-italic">{record.mapped_at}</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded shadow px-5 py-4">
      <div className="flex flex-col gap-3">
        {record.exposures.map((exp) => (
          <div key={exp.ticker} className="border-b last:border-0 pb-3 last:pb-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Link
                to={`/exposures/${exp.ticker}`}
                className="font-mono font-semibold text-sm hover:underline"
              >
                {exp.ticker}
              </Link>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${EXPOSURE_TYPE_COLORS[exp.exposure_type] ?? "bg-gray-100 text-gray-700"}`}>
                {exp.exposure_type}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${STRENGTH_COLORS[exp.exposure_strength] ?? "bg-gray-100 text-gray-700"}`}>
                {exp.exposure_strength}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${CONFIDENCE_COLORS[exp.confidence] ?? "bg-gray-100 text-gray-700"}`}>
                {exp.confidence} confidence
              </span>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {ROLE_LABELS[exp.business_role] ?? exp.business_role}
              </span>
            </div>
            <p className="text-sm text-gray-700 mb-1">{exp.rationale}</p>
            <div className="flex gap-1 flex-wrap">
              {exp.dimensions_implicated.map((d) => (
                <DimensionBadge key={d} dimension={d} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="text-xs text-gray-400 mt-3 flex items-center justify-between">
        <span>Mapped {record.mapped_at}</span>
        <Link
          to={`/items/${record.item_id}`}
          className="hover:underline text-gray-500"
        >
          View analysis →
        </Link>
      </div>
    </div>
  );
}

export default function ExposureList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const ticker = params.get("ticker") ?? "";
  const exposureType = params.get("exposure_type") ?? "";

  const [data, setData] = useState<ExposureListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchExposures({
      page,
      ticker: ticker || undefined,
      exposure_type: exposureType || undefined,
    })
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load exposures");
      });
  }, [page, ticker, exposureType]);

  function goPage(p: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
  }

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.set("page", "1");
    setParams(next);
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h1 className="text-2xl font-semibold">Structural Exposures</h1>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            placeholder="Filter by ticker…"
            value={ticker}
            onChange={(e) => setFilter("ticker", e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm w-40"
          />
          <select
            value={exposureType}
            onChange={(e) => setFilter("exposure_type", e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            <option value="">All types</option>
            <option value="direct">Direct</option>
            <option value="indirect">Indirect</option>
            <option value="contextual">Contextual</option>
          </select>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">{data.total} record{data.total !== 1 ? "s" : ""}</p>

      {data.exposures.length === 0 ? (
        <p className="text-gray-500">No exposure records found.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.exposures.map((record) => (
            <ExposureRow key={record.id} record={record} />
          ))}
        </div>
      )}

      <Pagination page={data.page} pages={data.pages} onPage={goPage} />
    </div>
  );
}
