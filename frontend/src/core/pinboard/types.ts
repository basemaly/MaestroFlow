export interface PinboardBookmark {
  url: string;
  url_normalized: string;
  title: string;
  description: string;
  tags: string[];
  created_at?: string | null;
  shared: boolean;
  toread: boolean;
  extended?: string | null;
  fingerprint: string;
  already_imported?: boolean;
  imported_document_id?: string | null;
}

export interface PinboardConfigResponse {
  base_url: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  warning?: string | null;
  health?: {
    configured: boolean;
    available: boolean;
    healthy: boolean;
    summary: string;
    last_error?: string | null;
  };
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface PinboardSearchResponse {
  items: PinboardBookmark[];
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface PinboardPreviewImportResponse extends PinboardSearchResponse {
  target_search_space_id?: number | null;
  resolved_search_space_id?: number | null;
  project_key?: string | null;
  can_import: boolean;
  summary?: {
    total: number;
    new_items: number;
    already_imported: number;
  };
}

export interface PinboardImportResponse {
  items: Array<PinboardBookmark & { status?: string; reason?: string; surfsense_document_id?: string | null }>;
  imported: number;
  skipped: number;
  failed: number;
  target_search_space_id?: number | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}
