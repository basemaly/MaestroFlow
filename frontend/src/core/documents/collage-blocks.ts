/**
 * Shared collage block persistence — used by both CollageWorkspace and BlocksSidebar.
 * Backed by localStorage keyed per document.
 */

export type BlockSource = "surfsense" | "calibre" | "chat" | "pasted" | "manual" | "pinboard";

export interface CollageBlock {
  id: string;
  source: BlockSource;
  title: string;
  content: string;
  addedAt: number;
  /** Board mode position. Undefined means unplaced (auto-stacked in list mode). */
  x?: number;
  y?: number;
}

const KEY = (docId: string) => `maestroflow:collage:${docId}`;

export function loadBlocks(docId: string): CollageBlock[] {
  try {
    const raw = localStorage.getItem(KEY(docId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as CollageBlock[]) : [];
  } catch {
    return [];
  }
}

export function saveBlocks(docId: string, blocks: CollageBlock[]): void {
  try {
    localStorage.setItem(KEY(docId), JSON.stringify(blocks));
  } catch {
    // ignore quota errors
  }
}

export function addBlock(docId: string, partial: Omit<CollageBlock, "id" | "addedAt">): CollageBlock {
  const block: CollageBlock = {
    ...partial,
    id: crypto.randomUUID(),
    addedAt: Date.now(),
  };
  saveBlocks(docId, [...loadBlocks(docId), block]);
  return block;
}

export function removeBlock(docId: string, blockId: string): CollageBlock[] {
  const updated = loadBlocks(docId).filter((b) => b.id !== blockId);
  saveBlocks(docId, updated);
  return updated;
}
