import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchItems } from "../api/client";
import type { ItemListResponse, ItemsParams } from "../types/api";
import DimensionBadge from "../components/DimensionBadge";
import ImportanceBadge from "../components/ImportanceBadge";
import ChangeTypeBadge from "../components/ChangeTypeBadge";
import Pagination from "../components/Pagination";
import FilterBar from "../components/FilterBar";

export default function ItemList() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<ItemListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const p: ItemsParams = {};
    for (const [k, v] of params.entries()) {
      if (v) (p as Record<string, string>)[k] = v;
    }
    if (!p.page) p.page = 1;
    fetchItems(p)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load items");
      });
  }, [params]);

  function goPage(p: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
  }

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Items</h1>
      <FilterBar />
      {!data ? (
        <p className="text-gray-500">Loading...</p>
      ) : data.items.length === 0 ? (
        <p className="text-gray-500">No items match the current filters.</p>
      ) : (
        <>
          <p className="text-sm text-gray-500 mb-3">{data.total} results</p>
          <div className="space-y-3">
            {data.items.map((item) => (
              <Link
                key={item.id}
                to={`/items/${item.id}`}
                className="block bg-white rounded shadow px-4 py-3 hover:ring-2 hover:ring-gray-300"
              >
                <div className="flex justify-between items-start gap-2">
                  <h3 className="font-medium text-sm">{item.title}</h3>
                  <ImportanceBadge importance={item.importance} />
                </div>
                <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                  {item.summary}
                </p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  {item.dimensions.map((d) => (
                    <DimensionBadge key={d.dimension} dimension={d.dimension} />
                  ))}
                  <ChangeTypeBadge changeType={item.change_type} />
                  <span className="text-xs text-gray-400 ml-auto">
                    {item.source_name} &middot; {item.timestamp.slice(0, 10)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
          <Pagination page={data.page} pages={data.pages} onPage={goPage} />
        </>
      )}
    </div>
  );
}
