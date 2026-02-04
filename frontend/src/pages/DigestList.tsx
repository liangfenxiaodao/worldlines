import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchDigests } from "../api/client";
import type { DigestListResponse } from "../types/api";
import { dimensionLabel } from "../components/DimensionBadge";
import Pagination from "../components/Pagination";

export default function DigestList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const [data, setData] = useState<DigestListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDigests(page)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load digests");
      });
  }, [page]);

  function goPage(p: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Digests</h1>
      {data.digests.length === 0 ? (
        <p className="text-gray-500">No digests yet.</p>
      ) : (
        <div className="space-y-3">
          {data.digests.map((d) => (
            <Link
              key={d.id}
              to={`/digests/${d.digest_date}`}
              className="block bg-white rounded shadow px-4 py-3 hover:ring-2 hover:ring-gray-300"
            >
              <div className="flex justify-between items-baseline">
                <span className="font-medium">{d.digest_date}</span>
                <span className="text-sm text-gray-500">
                  {d.item_count} items
                </span>
              </div>
              <div className="flex flex-wrap gap-2 mt-2 text-xs text-gray-500">
                {Object.entries(d.dimension_breakdown).map(([dim, count]) => (
                  <span key={dim}>
                    {dimensionLabel(dim)}: {count}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}
      <Pagination page={data.page} pages={data.pages} onPage={goPage} />
    </div>
  );
}
