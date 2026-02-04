import { useSearchParams } from "react-router-dom";

const DIMENSIONS = [
  { value: "compute_and_computational_paradigms", label: "Compute" },
  { value: "capital_flows_and_business_models", label: "Capital" },
  { value: "energy_resources_and_physical_constraints", label: "Energy" },
  { value: "technology_adoption_and_industrial_diffusion", label: "Tech Adoption" },
  { value: "governance_regulation_and_societal_response", label: "Governance" },
];

const CHANGE_TYPES = ["reinforcing", "friction", "early_signal", "neutral"];
const IMPORTANCE = ["high", "medium", "low"];
const TIME_HORIZONS = ["short", "medium", "long"];
const SORT_OPTIONS = [
  { value: "analyzed_at", label: "Analyzed at" },
  { value: "importance", label: "Importance" },
  { value: "timestamp", label: "Timestamp" },
];

export default function FilterBar() {
  const [params, setParams] = useSearchParams();

  function set(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("page");
    setParams(next);
  }

  function clear() {
    setParams({});
  }

  const selectClass =
    "text-sm border border-gray-300 rounded px-2 py-1 bg-white";
  const inputClass =
    "text-sm border border-gray-300 rounded px-2 py-1";

  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Dimension
        <select
          className={selectClass}
          value={params.get("dimension") ?? ""}
          onChange={(e) => set("dimension", e.target.value)}
        >
          <option value="">All</option>
          {DIMENSIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Change type
        <select
          className={selectClass}
          value={params.get("change_type") ?? ""}
          onChange={(e) => set("change_type", e.target.value)}
        >
          <option value="">All</option>
          {CHANGE_TYPES.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Importance
        <select
          className={selectClass}
          value={params.get("importance") ?? ""}
          onChange={(e) => set("importance", e.target.value)}
        >
          <option value="">All</option>
          {IMPORTANCE.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Time horizon
        <select
          className={selectClass}
          value={params.get("time_horizon") ?? ""}
          onChange={(e) => set("time_horizon", e.target.value)}
        >
          <option value="">All</option>
          {TIME_HORIZONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        From
        <input
          type="date"
          className={inputClass}
          value={params.get("date_from") ?? ""}
          onChange={(e) => set("date_from", e.target.value)}
        />
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        To
        <input
          type="date"
          className={inputClass}
          value={params.get("date_to") ?? ""}
          onChange={(e) => set("date_to", e.target.value)}
        />
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Sort
        <select
          className={selectClass}
          value={params.get("sort") ?? "analyzed_at"}
          onChange={(e) => set("sort", e.target.value)}
        >
          {SORT_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1 text-xs text-gray-500">
        Order
        <select
          className={selectClass}
          value={params.get("order") ?? "desc"}
          onChange={(e) => set("order", e.target.value)}
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </label>

      <button
        onClick={clear}
        className="text-sm text-gray-500 underline hover:text-gray-700 pb-1"
      >
        Clear all
      </button>
    </div>
  );
}
