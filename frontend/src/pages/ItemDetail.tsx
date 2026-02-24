import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchItem } from "../api/client";
import type { ExposureEntry, ItemDetailResponse, TemporalLinkEntry } from "../types/api";
import DimensionBadge from "../components/DimensionBadge";
import ImportanceBadge from "../components/ImportanceBadge";
import ChangeTypeBadge from "../components/ChangeTypeBadge";

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

const LINK_TYPE_COLORS: Record<string, string> = {
  reinforces: "bg-green-100 text-green-800",
  contradicts: "bg-red-100 text-red-800",
  extends: "bg-blue-100 text-blue-800",
  supersedes: "bg-gray-100 text-gray-600",
};

function TemporalLinkCard({ entry }: { entry: TemporalLinkEntry }) {
  const directionLabel = entry.direction === "incoming" ? "Earlier signal" : "Later observation";
  return (
    <div className="border border-gray-200 rounded px-4 py-3">
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className="text-xs text-gray-400">{directionLabel}</span>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${LINK_TYPE_COLORS[entry.link_type] ?? "bg-gray-100 text-gray-700"}`}>
          {entry.link_type}
        </span>
      </div>
      <Link
        to={`/items/${entry.linked_item_id}`}
        className="text-sm font-medium hover:underline"
      >
        {entry.linked_item_title}
      </Link>
      <p className="text-xs text-gray-500 mt-0.5">
        {entry.linked_item_source} &middot; {entry.linked_item_timestamp}
      </p>
      <p className="text-sm text-gray-600 mt-1">{entry.rationale}</p>
    </div>
  );
}

function ExposureCard({ exp }: { exp: ExposureEntry }) {
  return (
    <div className="border border-gray-200 rounded px-4 py-3">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="font-mono font-semibold text-sm">{exp.ticker}</span>
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
      <p className="text-sm text-gray-700 mb-2">{exp.rationale}</p>
      <div className="flex gap-1 flex-wrap">
        {exp.dimensions_implicated.map((d) => (
          <DimensionBadge key={d} dimension={d} />
        ))}
      </div>
    </div>
  );
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ItemDetailResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    fetchItem(id)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load item");
      });
  }, [id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  const { item, analysis, exposure } = data;

  return (
    <div>
      <Link to="/items" className="text-sm text-gray-500 hover:underline">
        &larr; Items
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-1">{item.title}</h1>
      <p className="text-sm text-gray-500 mb-4">
        {item.source_name} &middot; {item.source_type} &middot;{" "}
        {item.timestamp}
        {item.canonical_link && (
          <>
            {" "}
            &middot;{" "}
            <a
              href={item.canonical_link}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              Source
            </a>
          </>
        )}
      </p>

      <div className="bg-white rounded shadow px-5 py-4 mb-6">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Content</h2>
        <p className="text-sm whitespace-pre-wrap">{item.content}</p>
      </div>

      {analysis && (
        <div className="bg-white rounded shadow px-5 py-4">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Analysis</h2>

          <p className="text-sm mb-4">{analysis.summary}</p>

          <div className="flex flex-wrap gap-2 mb-4">
            {analysis.dimensions.map((d) => (
              <DimensionBadge key={d.dimension} dimension={d.dimension} />
            ))}
            <ChangeTypeBadge changeType={analysis.change_type} />
            <ImportanceBadge importance={analysis.importance} />
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {analysis.time_horizon}
            </span>
          </div>

          {analysis.key_entities.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs text-gray-500 uppercase mb-1">
                Key entities
              </h3>
              <p className="text-sm">{analysis.key_entities.join(", ")}</p>
            </div>
          )}

          <div className="text-xs text-gray-400">
            Analyzed {analysis.analyzed_at} &middot; v{analysis.analysis_version}
          </div>
        </div>
      )}

      {exposure && exposure.exposures.length > 0 && (
        <div className="bg-white rounded shadow px-5 py-4 mt-6">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Structural Exposures</h2>
          <div className="flex flex-col gap-3">
            {exposure.exposures.map((exp) => (
              <ExposureCard key={exp.ticker} exp={exp} />
            ))}
          </div>
          <div className="text-xs text-gray-400 mt-3">Mapped {exposure.mapped_at}</div>
        </div>
      )}

      {exposure && exposure.skipped_reason && (
        <div className="bg-white rounded shadow px-5 py-4 mt-6">
          <h2 className="text-sm font-medium text-gray-700 mb-1">Structural Exposures</h2>
          <p className="text-sm text-gray-500 italic">{exposure.skipped_reason}</p>
          <div className="text-xs text-gray-400 mt-2">Mapped {exposure.mapped_at}</div>
        </div>
      )}

      {data.temporal_links && data.temporal_links.length > 0 && (
        <div className="bg-white rounded shadow px-5 py-4 mt-6">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Related observations</h2>
          <div className="flex flex-col gap-3">
            {data.temporal_links.map((entry) => (
              <TemporalLinkCard key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400 mt-4">
        Ingested {item.ingested_at} &middot; Hash {item.dedup_hash}
      </div>
    </div>
  );
}
