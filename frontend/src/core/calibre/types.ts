export interface HealthEnvelope {
  configured: boolean;
  available: boolean;
  healthy?: boolean;
  summary: string;
  details?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  last_error?: string | null;
}

export interface ErrorEnvelope {
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface CalibreStatusResponse {
  available: boolean;
  configured?: boolean;
  healthy?: boolean;
  dataset_name?: string;
  dataset_id?: string;
  collection?: string;
  indexed_books?: number;
  indexed_chunks?: number;
  last_sync_at?: string | null;
  last_error?: string | null;
  health?: HealthEnvelope;
  error?: ErrorEnvelope | null;
}

export interface CalibreBook {
  id: string | number;
  title: string;
  authors?: string[];
  series?: string;
  series_index?: number;
  tags?: string[];
  publisher?: string;
  published_date?: string;
  isbn?: string;
  description?: string;
  cover_url?: string;
  filepath?: string;
  file_size?: number;
  formats?: string[];
  rating?: number;
  language?: string;
}

export interface CalibreQueryResponse {
  items: CalibreBook[];
  total: number;
  dataset_name?: string;
  warning?: string | null;
  health?: HealthEnvelope;
  error?: ErrorEnvelope | null;
}

export interface CalibreBrowseMetadata {
  authors: string[];
  tags: string[];
  series: string[];
  publishers?: string[];
}

export type CalibreBookSelection = Record<string | number, boolean>;

export interface CalibreIngestTarget {
  project_key?: string;
  search_space_id?: number;
}
