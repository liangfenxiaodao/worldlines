import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { fetchTickerIndex } from "../api/client";
import type { TickerIndexEntry, TickerIndexResponse } from "../types/api";

const SORT_OPTIONS = [
  { value: "count", label: "By article count" },
  { value: "ticker", label: "Alphabetical" },
  { value: "recent", label: "Most recently seen" },
];

function countBadgeColor(count: number): string {
  if (count >= 10) return "bg-indigo-100 text-indigo-800";
  if (count >= 4) return "bg-amber-100 text-amber-800";
  return "bg-gray-100 text-gray-600";
}

function TickerCard({ entry }: { entry: TickerIndexEntry }) {
  return (
    <Link
      to={`/exposures/${entry.ticker}`}
      className="bg-white rounded shadow px-4 py-3 flex flex-col gap-1 hover:shadow-md transition-shadow"
    >
      <span className="font-mono font-bold text-lg">{entry.ticker}</span>
      <div className="flex items-center gap-2">
        <span
          className={`text-xs px-2 py-0.5 rounded font-medium ${countBadgeColor(entry.article_count)}`}
        >
          {entry.article_count} article{entry.article_count !== 1 ? "s" : ""}
        </span>
      </div>
      <span className="text-xs text-gray-400">{entry.last_mapped_at.slice(0, 10)}</span>
    </Link>
  );
}

export default function TickerIndex() {
  const [params, setParams] = useSearchParams();
  const sort = params.get("sort") ?? "count";
  const query = params.get("q") ?? "";

  const [data, setData] = useState<TickerIndexResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    fetchTickerIndex(sort)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load ticker index");
      });
  }, [sort]);

  function setSort(value: string) {
    const next = new URLSearchParams(params);
    next.set("sort", value);
    setParams(next);
  }

  function setQuery(value: string) {
    const next = new URLSearchParams(params);
    if (value) {
      next.set("q", value);
    } else {
      next.delete("q");
    }
    setParams(next);
  }

  const filtered = data
    ? data.tickers.filter((t) =>
        query ? t.ticker.toLowerCase().includes(query.toLowerCase()) : true,
      )
    : [];

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="mb-5">
        <Link to="/exposures" className="text-sm text-gray-500 hover:underline">
          ← Exposures
        </Link>
      </div>

      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Ticker Index</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {filtered.length} of {data.total} ticker{data.total !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            placeholder="Filter…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm w-32"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-gray-500">No tickers found.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filtered.map((entry) => (
            <TickerCard key={entry.ticker} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
