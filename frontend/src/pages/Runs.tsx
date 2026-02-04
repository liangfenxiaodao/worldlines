import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchRuns } from "../api/client";
import type { PipelineRunListResponse } from "../types/api";
import Pagination from "../components/Pagination";

const TYPE_COLORS: Record<string, string> = {
  ingestion: "bg-blue-100 text-blue-800",
  analysis: "bg-purple-100 text-purple-800",
  digest: "bg-amber-100 text-amber-800",
};

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  const secs = Math.round(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  return `${mins}m ${rem}s`;
}

function resultSummary(result: Record<string, unknown>): string {
  return Object.entries(result)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
    .join(", ");
}

export default function Runs() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const runType = params.get("run_type") ?? "";
  const [data, setData] = useState<PipelineRunListResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchRuns({
      page,
      run_type: runType || undefined,
    })
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load runs");
      });
  }, [page, runType]);

  function goPage(p: number) {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    setParams(next);
  }

  function setFilter(type: string) {
    const next = new URLSearchParams(params);
    if (type) {
      next.set("run_type", type);
    } else {
      next.delete("run_type");
    }
    next.set("page", "1");
    setParams(next);
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Pipeline Runs</h1>
        <select
          value={runType}
          onChange={(e) => setFilter(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm"
        >
          <option value="">All types</option>
          <option value="ingestion">Ingestion</option>
          <option value="analysis">Analysis</option>
          <option value="digest">Digest</option>
        </select>
      </div>

      {data.runs.length === 0 ? (
        <p className="text-gray-500">No pipeline runs recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4">Time</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Duration</th>
                <th className="py-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {data.runs.map((run) => (
                <tr key={run.id} className="border-b hover:bg-gray-50">
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-600">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[run.run_type] ?? "bg-gray-100 text-gray-800"}`}
                    >
                      {run.run_type}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <span className="flex items-center gap-1">
                      <span
                        className={`inline-block w-2 h-2 rounded-full ${run.status === "success" ? "bg-green-500" : "bg-red-500"}`}
                      />
                      {run.status}
                    </span>
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatDuration(run.started_at, run.finished_at)}
                  </td>
                  <td className="py-2 text-gray-600">
                    {run.error ? (
                      <span className="text-red-600">{run.error}</span>
                    ) : (
                      resultSummary(run.result)
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={data.page} pages={data.pages} onPage={goPage} />
    </div>
  );
}
