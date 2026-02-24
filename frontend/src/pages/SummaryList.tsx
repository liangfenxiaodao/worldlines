import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchSummaries } from "../api/client";
import type { PeriodicSummary, PeriodicSummaryListResponse } from "../types/api";
import { dimensionLabel } from "../components/DimensionBadge";
import Pagination from "../components/Pagination";

function SummaryCard({ s }: { s: PeriodicSummary }) {
  const total = Object.values(s.dimension_breakdown).reduce((a, b) => a + b, 0) || 1;
  const since = s.since.slice(0, 10);
  const until = s.until.slice(0, 10);

  return (
    <div className="bg-white rounded shadow px-5 py-4">
      <div className="flex items-baseline justify-between mb-1 flex-wrap gap-2">
        <h2 className="font-semibold text-base">
          {s.window_days}-day summary
        </h2>
        <span className="text-xs text-gray-400">{since} → {until}</span>
      </div>
      <p className="text-xs text-gray-400 mb-4">
        {s.item_count} observations surfaced
      </p>

      {/* Dimension breakdown */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
          Signal density
        </p>
        <div className="flex flex-col gap-1">
          {Object.entries(s.dimension_breakdown)
            .sort(([, a], [, b]) => b - a)
            .map(([dim, count]) => {
              const pct = Math.round((count / total) * 100);
              return (
                <div key={dim} className="flex items-center gap-2">
                  <div className="w-36 text-xs text-gray-600 truncate">
                    {dimensionLabel(dim)}
                  </div>
                  <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-gray-500 h-1.5 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="text-xs text-gray-400 w-12 text-right">
                    {count} ({pct}%)
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Change type distribution */}
      {Object.keys(s.change_type_distribution).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(s.change_type_distribution)
            .sort(([, a], [, b]) => b - a)
            .map(([ct, count]) => (
              <span key={ct} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                {ct}: {count}
              </span>
            ))}
        </div>
      )}

      {/* Synthesis */}
      {s.summary_en && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Synthesis
          </p>
          <p className="text-sm text-gray-700">{s.summary_en}</p>
        </div>
      )}
      {s.summary_zh && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            综合
          </p>
          <p className="text-sm text-gray-700">{s.summary_zh}</p>
        </div>
      )}

      <p className="text-xs text-gray-400 mt-3">Sent {s.sent_at.slice(0, 16).replace("T", " ")} UTC</p>
    </div>
  );
}

export default function SummaryList() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const [data, setData] = useState<PeriodicSummaryListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSummaries(page)
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load summaries");
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
      <h1 className="text-2xl font-semibold mb-1">Periodic Summaries</h1>
      <p className="text-sm text-gray-500 mb-5">
        Structural synthesis across all dimensions over rolling time windows.
      </p>

      {data.summaries.length === 0 ? (
        <p className="text-gray-500">No summaries yet — the first will appear after the next scheduled run.</p>
      ) : (
        <div className="flex flex-col gap-5">
          {data.summaries.map((s) => (
            <SummaryCard key={s.id} s={s} />
          ))}
        </div>
      )}

      <Pagination page={data.page} pages={data.pages} onPage={goPage} />
    </div>
  );
}
