// Types matching the Pydantic response models in src/worldlines/web/models.py

export interface StatsResponse {
  total_items: number;
  total_analyses: number;
  total_digests: number;
  latest_digest_date: string | null;
  dimension_breakdown: Record<string, number>;
  change_type_distribution: Record<string, number>;
  importance_distribution: Record<string, number>;
}

export interface DigestSummary {
  id: string;
  digest_date: string;
  item_count: number;
  dimension_breakdown: Record<string, number>;
  change_type_distribution: Record<string, number>;
  sent_at: string;
}

export interface DigestDetail extends DigestSummary {
  high_importance_items: Record<string, unknown>[];
  summary_en: string | null;
  summary_zh: string | null;
  message_text: string;
  telegram_message_ids: number[];
}

export interface DigestListResponse {
  digests: DigestSummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface DimensionEntry {
  dimension: string;
  relevance: string;
}

export interface ItemSummary {
  id: string;
  analysis_id: string;
  title: string;
  source_name: string;
  source_type: string;
  timestamp: string;
  canonical_link: string | null;
  summary: string;
  dimensions: DimensionEntry[];
  change_type: string;
  time_horizon: string;
  importance: string;
  analyzed_at: string;
}

export interface ItemListResponse {
  items: ItemSummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ItemDetail {
  id: string;
  title: string;
  source_name: string;
  source_type: string;
  timestamp: string;
  content: string;
  canonical_link: string | null;
  ingested_at: string;
  dedup_hash: string;
}

export interface AnalysisDetail {
  id: string;
  dimensions: DimensionEntry[];
  change_type: string;
  time_horizon: string;
  summary: string;
  importance: string;
  key_entities: string[];
  analyzed_at: string;
  analysis_version: string;
}

export interface ItemDetailResponse {
  item: ItemDetail;
  analysis: AnalysisDetail | null;
}

export interface PipelineRun {
  id: string;
  run_type: string;
  started_at: string;
  finished_at: string;
  status: string;
  result: Record<string, unknown>;
  error: string | null;
}

export interface PipelineRunListResponse {
  runs: PipelineRun[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface RunsParams {
  run_type?: string;
  page?: number;
  per_page?: number;
}

export interface ItemsParams {
  dimension?: string;
  change_type?: string;
  importance?: string;
  time_horizon?: string;
  source_type?: string;
  date_from?: string;
  date_to?: string;
  sort?: string;
  order?: string;
  page?: number;
  per_page?: number;
}
