export interface DocEditOpenDetail {
  content: string;
}

const DOC_EDIT_OPEN_EVENT = "maestroflow:doc-edit-open";

export function openDocEditStudio(detail: DocEditOpenDetail) {
  window.dispatchEvent(new CustomEvent<DocEditOpenDetail>(DOC_EDIT_OPEN_EVENT, { detail }));
}

export { DOC_EDIT_OPEN_EVENT };
