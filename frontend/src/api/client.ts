import type {
  DigestDetail,
  DigestListResponse,
  DimensionDetail,
  DimensionOverview,
  ExposureListResponse,
  ExposuresParams,
  ItemDetailResponse,
  ItemListResponse,
  ItemsParams,
  PeriodicSummaryListResponse,
  PipelineRunListResponse,
  RunsParams,
  StatsResponse,
  TickerExposureResponse,
  TickerIndexResponse,
} from "../types/api";

const BASE = "/api/v1";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function fetchStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/stats");
}

export function fetchDigests(
  page = 1,
  perPage = 20,
): Promise<DigestListResponse> {
  return request<DigestListResponse>(
    `/digests?page=${page}&per_page=${perPage}`,
  );
}

export function fetchDigest(date: string): Promise<DigestDetail> {
  return request<DigestDetail>(`/digests/${encodeURIComponent(date)}`);
}

export function fetchItems(params: ItemsParams = {}): Promise<ItemListResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      qs.set(k, String(v));
    }
  }
  const q = qs.toString();
  return request<ItemListResponse>(`/items${q ? `?${q}` : ""}`);
}

export function fetchItem(id: string): Promise<ItemDetailResponse> {
  return request<ItemDetailResponse>(`/items/${encodeURIComponent(id)}`);
}

export function fetchExposures(params: ExposuresParams = {}): Promise<ExposureListResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      qs.set(k, String(v));
    }
  }
  const q = qs.toString();
  return request<ExposureListResponse>(`/exposures${q ? `?${q}` : ""}`);
}

export function fetchTickerIndex(sort = "count"): Promise<TickerIndexResponse> {
  return request<TickerIndexResponse>(`/exposures/tickers?sort=${encodeURIComponent(sort)}`);
}

export function fetchTickerExposures(
  ticker: string,
  params: { page?: number; per_page?: number } = {},
): Promise<TickerExposureResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const q = qs.toString();
  return request<TickerExposureResponse>(
    `/exposures/ticker/${encodeURIComponent(ticker)}${q ? `?${q}` : ""}`,
  );
}

export function fetchSummaries(
  page = 1,
  perPage = 20,
): Promise<PeriodicSummaryListResponse> {
  return request<PeriodicSummaryListResponse>(
    `/summaries?page=${page}&per_page=${perPage}`,
  );
}

export function fetchDimensions(): Promise<DimensionOverview> {
  return request<DimensionOverview>("/dimensions");
}

export function fetchDimensionDetail(dimension: string): Promise<DimensionDetail> {
  return request<DimensionDetail>(`/dimensions/${encodeURIComponent(dimension)}`);
}

export function fetchRuns(params: RunsParams = {}): Promise<PipelineRunListResponse> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      qs.set(k, String(v));
    }
  }
  const q = qs.toString();
  return request<PipelineRunListResponse>(`/runs${q ? `?${q}` : ""}`);
}
