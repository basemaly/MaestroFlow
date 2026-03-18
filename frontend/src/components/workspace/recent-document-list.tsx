"use client";

import Link from "next/link";

import { useDocuments } from "@/core/documents/hooks";

export function RecentDocumentList() {
  const { data } = useDocuments();
  const documents = data?.documents?.slice(0, 5) ?? [];

  if (documents.length === 0) {
    return null;
  }

  return (
    <div className="px-2 pb-2">
      <div className="text-muted-foreground px-2 pb-2 text-xs font-medium uppercase tracking-[0.16em]">
        Documents
      </div>
      <div className="space-y-1">
        {documents.map((documentRecord) => (
          <Link
            key={documentRecord.doc_id}
            href={`/workspace/docs/${documentRecord.doc_id}`}
            className="text-muted-foreground hover:bg-accent/40 block rounded-md px-2 py-1.5 text-sm"
          >
            <div className="truncate">{documentRecord.title}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
