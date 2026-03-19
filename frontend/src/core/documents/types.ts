export interface DocumentRecord {
  doc_id: string;
  title: string;
  content_markdown: string;
  editor_json?: Record<string, unknown> | null;
  writing_memory: string;
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

export interface DocumentQuickAction {
  action_id: string;
  name: string;
  instruction: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentQuickActionsListResponse {
  actions: DocumentQuickAction[];
}

export interface DocumentSnapshot {
  snapshot_id: string;
  doc_id: string;
  label: string;
  note?: string | null;
  source: string;
  title: string;
  content_markdown: string;
  editor_json?: Record<string, unknown> | null;
  writing_memory: string;
  created_at: string;
}

export interface DocumentSnapshotsListResponse {
  snapshots: DocumentSnapshot[];
}

export type DocumentTransformOperation =
  | "rewrite"
  | "shorten"
  | "expand"
  | "improve-clarity"
  | "executive-summary"
  | "bullets"
  | "custom";
