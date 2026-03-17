export interface Snippet {
  id: string;
  text: string;
  label: string;
  tags: string[];
  source_thread_id?: string;
  created_at: number;
}
