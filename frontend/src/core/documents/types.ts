export interface DocumentRecord {
  doc_id: string;
  title: string;
  content_markdown: string;
  editor_json?: Record<string, unknown> | null;
  status: string;
  source_run_id?: string | null;
  source_version_id?: string | null;
  source_thread_id?: string | null;
  source_filepath?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentsListResponse {
  documents: DocumentRecord[];
}

export type DocumentTransformOperation =
  | "rewrite"
  | "shorten"
  | "expand"
  | "improve-clarity"
  | "executive-summary"
  | "bullets"
  | "custom";
