import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchItem } from "../api/client";
import type { ItemDetailResponse } from "../types/api";
import DimensionBadge from "../components/DimensionBadge";
import ImportanceBadge from "../components/ImportanceBadge";
import ChangeTypeBadge from "../components/ChangeTypeBadge";

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

  const { item, analysis } = data;

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

      <div className="text-xs text-gray-400 mt-4">
        Ingested {item.ingested_at} &middot; Hash {item.dedup_hash}
      </div>
    </div>
  );
}
