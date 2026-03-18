# MaestroFlow Notion-Style Block Editor Implementation Plan

## Summary

MaestroFlow should add a block-based editing layer on top of the existing doc-edit workflow rather than replace the current workflow-first model.

The current system is already strong at:

- whole-document ingestion
- parallel editorial runs
- human review and explicit winner selection
- artifact preview and export

The missing capability is a structured post-selection editing surface where humans and agents can refine the chosen output block by block.

This plan proposes a staged implementation on branch `codex/notion` with these principles:

1. Keep the existing markdown-based doc-edit backend working.
2. Introduce a Tiptap-powered block editor in the frontend as the new editing surface.
3. Preserve markdown as the canonical interchange format in Phase 1.
4. Add optional block-aware persistence and block-level AI actions in later phases.

## Why This Approach

MaestroFlow currently uses a plain `Textarea` for doc input and a version-selection workflow in the doc-edit studio. The relevant surfaces are:

- `frontend/src/components/workspace/doc-edit-dialog.tsx`
- `frontend/src/app/workspace/doc-edits/page.tsx`
- `frontend/src/app/workspace/doc-edits/[run_id]/page.tsx`
- `frontend/src/components/workspace/artifacts/artifact-file-detail.tsx`
- `backend/src/gateway/routers/doc_editing.py`
- `backend/src/doc_editing/state.py`

The current model is whole-document and markdown-oriented. The new editor should fit that model first, then extend it with richer structure once the UX is proven.

## Product Goals

### Primary goals

- Turn doc-edit from a compare-and-select tool into a compare-select-refine workflow.
- Make markdown artifacts editable inside MaestroFlow with a modern block UI.
- Let users and AI operate on selected sections instead of rerunning whole-document rewrites for small edits.
- Preserve compatibility with current run artifacts, SurfSense export, and markdown previews.

### Non-goals for initial release

- Real-time multi-user collaboration
- full Google Docs parity
- arbitrary rich layout/page design
- replacing markdown as the only export format
- rewriting the entire doc-edit backend graph before the editor ships

## Recommended Editor Stack

### Recommendation

Use Tiptap, not BlockNote, for the first implementation.

### Rationale

- DeerFlow’s prior “Notion-like block editing” claim referenced Tiptap.
- Tiptap gives lower-level control over schema, markdown conversion, and AI actions.
- MaestroFlow already has a markdown-first artifact and doc-edit model, so a flexible ProseMirror layer is a better fit than adopting a more opinionated block editor abstraction.
- We can still deliver a Notion-style UX with slash commands, block handles, callouts, lists, toggles, task items, and code blocks.

### Initial dependency set

- `@tiptap/react`
- `@tiptap/pm`
- `@tiptap/starter-kit`
- `@tiptap/extension-placeholder`
- `@tiptap/extension-task-list`
- `@tiptap/extension-task-item`
- `@tiptap/extension-table`
- `@tiptap/extension-table-row`
- `@tiptap/extension-table-cell`
- `@tiptap/extension-table-header`
- `@tiptap/extension-code-block-lowlight`
- `@tiptap/extension-underline`
- markdown conversion utilities compatible with Tiptap

### Deferred dependencies

- Yjs collaboration
- comment/annotation packages
- full presence and multiplayer infrastructure

## Product Design

## Core user journeys

### 1. Start a doc-edit run

The user still pastes markdown or uploads a file in the existing studio.

No behavioral change is required for initial run creation.

### 2. Compare versions

The current side-by-side and diff views stay intact for review.

### 3. Open winning version in block editor

After the user selects a version, MaestroFlow opens a block-editor workspace seeded from the winning markdown.

### 4. Edit artifact directly

Any markdown artifact with the current “Edit in Doc Edit” action should open directly into the block editor instead of only reopening the raw markdown studio.

### 5. Apply AI to a selected block

The user highlights one or more blocks and invokes actions such as:

- rewrite
- shorten
- expand
- improve clarity
- preserve facts, improve style
- convert to executive summary

## UX surfaces to add

### New shared editor component

- `frontend/src/components/workspace/block-editor/`

Proposed files:

- `block-editor-shell.tsx`
- `block-editor.tsx`
- `block-editor-toolbar.tsx`
- `block-editor-slash-menu.tsx`
- `block-editor-inspector.tsx`
- `block-editor-commentary.tsx`
- `markdown-conversion.ts`
- `block-editor-types.ts`

### Doc-edit surface upgrade

`DocEditStudio` should evolve into a 3-stage surface:

1. Input
2. Review
3. Refine

For the first release:

- Input remains the existing left-side form.
- Review remains the existing version compare experience.
- Refine appears as a new tab or pane that activates once a version is selected.

### Artifact integration

`ArtifactFileDetail` should route markdown artifacts into the block editor experience with:

- source thread id
- source filepath
- initial markdown content
- optional read-only preview mode

### Dedicated route

Add a dedicated editing route:

- `frontend/src/app/workspace/docs/[doc_id]/page.tsx`

This prevents the editor from being trapped inside the modal/sheet experience and gives room for:

- larger canvas
- version history
- review sidebar
- block-level AI actions
- future comments and approvals

## Data Model Strategy

## Phase 1 canonical model

Keep markdown as the canonical document format across the backend.

The block editor runs in the frontend and serializes to markdown when:

- saving a draft
- starting a new edit pass
- exporting
- sending content to backend AI actions

### Why

- existing `DocEditRequest.document` already accepts a string
- existing run artifacts and finalization are markdown/file based
- SurfSense export already expects markdown-like output
- this avoids forcing a backend persistence migration before the UX is validated

## Phase 2 persistence model

Add optional persisted editor state for richer block behavior.

Recommended shape:

- `source_markdown`: latest markdown representation
- `editor_json`: Tiptap JSON document
- `doc_id`
- `title`
- `status`
- `source_run_id`
- `source_version_id`
- `created_at`
- `updated_at`

### Storage recommendation

Start with gateway-owned local persistence, parallel to current doc-edit metadata patterns.

Suggested location:

- `.deer-flow/documents.db`

Use SQLite first. Do not put this into the existing Executive database unless there is a clear governance reason to combine them.

## Backend Changes

## Phase 1 backend changes

Minimal backend changes:

1. Add draft-save endpoints for editable documents.
2. Add block-action endpoints that accept markdown snippets and return rewritten markdown.
3. Add document metadata endpoints for the new `/workspace/docs/[doc_id]` route.

### Proposed new router

- `backend/src/gateway/routers/documents.py`

### Proposed endpoints

- `POST /api/documents`
  - create document from markdown, artifact, or doc-edit winner
- `GET /api/documents/{doc_id}`
  - fetch metadata and content
- `PUT /api/documents/{doc_id}`
  - save markdown and optional editor JSON
- `POST /api/documents/{doc_id}/actions/rewrite-block`
  - rewrite selected block range
- `POST /api/documents/{doc_id}/actions/transform`
  - generic transform endpoint for shorten, expand, summarize, etc.

### Reuse current doc-edit APIs where possible

Do not overload `/api/doc-edit` with document management concerns. Keep that router focused on run orchestration.

## Phase 2 backend changes

### Extend doc-edit response contracts

Extend these structures:

- `DocEditStartResponse`
- `DocEditRun`
- `VersionRecord`

Add optional fields such as:

- `document_id`
- `source_document_id`
- `editor_ready`
- `refinement_status`

### Add structured review payloads

Current review payloads are version-level summaries. Add block-level suggestions later:

- `block_suggestions`
- `anchor_text`
- `anchor_path`
- `operation`
- `confidence`

## Frontend Changes

## Phase 1

### A. Add editor foundation

Create the block editor package under:

- `frontend/src/components/workspace/block-editor/`

Capabilities:

- paragraph, heading, bullet list, numbered list
- task list
- quote
- code block
- divider
- table
- callout
- slash command menu
- drag handle styling
- placeholder text
- markdown import/export

### B. Add document state hooks

New client module:

- `frontend/src/core/documents/`

Proposed files:

- `api.ts`
- `hooks.ts`
- `types.ts`

### C. Add full-page document route

Create:

- `frontend/src/app/workspace/docs/[doc_id]/page.tsx`

This route becomes the canonical editing canvas.

### D. Update doc-edit flow

In `DocEditStudio`:

- keep current run start flow
- keep current compare and select flow
- add “Open in Editor” after winner selection
- optionally auto-create a document draft when a version is selected

### E. Update artifact action

In `ArtifactFileDetail`:

- change “Edit in Doc Edit” behavior for markdown artifacts
- route to the document editor
- preserve the quick handoff experience from chat artifacts

## Phase 2

### Add block-level AI tools

New toolbar/selection actions:

- rewrite selection
- shorten selection
- expand selection
- improve tone
- turn section into bullets
- generate heading options
- transform into executive summary

### Add review side panel

The side panel should show:

- document outline
- block metadata
- AI suggestion history
- source run and version provenance

## Integration Plan

## Integration with current doc-edit workflow

### Existing workflow

1. Input document
2. Run multiple editorial skills
3. Compare versions
4. Select winner
5. Finalize/export

### Target workflow

1. Input document
2. Run multiple editorial skills
3. Compare versions
4. Select winner
5. Open winner in block editor
6. Refine specific sections with AI or manually
7. Save draft and export/publish

This keeps the existing supervised model intact while adding a stronger finishing step.

## Integration with artifacts

Markdown artifacts already expose an “Edit in Doc Edit” action. Reuse that affordance, but point it at the new document editor pipeline.

## Integration with SurfSense

Phase 1:

- export final markdown from the document editor

Phase 2:

- attach source document metadata and document ids to exported SurfSense records

## Migration and Rollout

## Phase 0: groundwork

### Deliverables

- choose Tiptap stack
- add plan and task files
- confirm route and persistence strategy
- confirm markdown conversion approach

### Acceptance criteria

- branch created
- plan approved
- no behavioral changes yet

## Phase 1: editor foundation

### Deliverables

- block editor component
- markdown import/export
- dedicated document route
- document API and SQLite persistence

### Acceptance criteria

- user can create a document from markdown
- user can edit and save it
- reloading restores content
- markdown export matches expected output format

## Phase 2: doc-edit integration

### Deliverables

- “Open in Editor” from selected doc-edit version
- “Edit in Doc Edit” artifact action rerouted to editor-backed document
- document provenance metadata

### Acceptance criteria

- a completed doc-edit run can be turned into an editable document in one click
- a markdown artifact from chat can be opened in the editor
- no regression in existing doc-edit run selection

## Phase 3: block-level AI actions

### Deliverables

- block selection actions
- backend transform endpoints
- prompt templates for block transforms

### Acceptance criteria

- user can rewrite a selected section without rerunning the whole document
- transforms preserve surrounding document structure
- failures degrade gracefully and do not lose document content

## Phase 4: advanced review and provenance

### Deliverables

- outline sidebar
- source run/version metadata
- suggestion history
- optional comment model

### Acceptance criteria

- user can trace content back to source run/version
- user can navigate long docs by outline

## Technical Risks

## 1. Markdown round-trip fidelity

Risk:

- some Tiptap structures will not map cleanly to markdown

Mitigation:

- restrict initial schema to markdown-safe blocks
- treat advanced block types as Phase 2+
- add snapshot tests for markdown import/export

## 2. Overloading doc-edit with document CRUD

Risk:

- the current orchestration API becomes messy if document storage and run orchestration are mixed

Mitigation:

- create a separate `documents` router and client module

## 3. Modal-based editor UX becoming cramped

Risk:

- trying to fit a real editor into the current dialog will produce a weak UX

Mitigation:

- use a full-page document route as the primary editor surface

## 4. Persisting block JSON too early

Risk:

- backend complexity increases before the product value is proven

Mitigation:

- Phase 1 keeps markdown canonical and block JSON optional

## 5. Accidental regression of current doc-edit flows

Risk:

- version compare and selection could break while the editor is added

Mitigation:

- keep existing route contracts stable
- add integration tests around run creation, selection, and editor handoff

## Verification Plan

## Frontend

- unit tests for markdown import/export helpers
- component tests for editor load/save behavior
- route tests for `/workspace/docs/[doc_id]`
- artifact handoff tests

## Backend

- API tests for document create/get/update
- API tests for block transform endpoints
- regression tests for `/api/doc-edit`

## End-to-end

- upload markdown -> run doc-edit -> select winner -> open editor -> save -> reload -> export
- open markdown artifact from chat -> edit -> save -> export to SurfSense

## Suggested Write Sequence

1. Add document API types and persistence.
2. Add Tiptap editor shell and markdown conversion.
3. Add `/workspace/docs/[doc_id]`.
4. Add editor create/save flows.
5. Wire doc-edit winner -> editor.
6. Wire artifact markdown -> editor.
7. Add block-level AI actions.
8. Add provenance sidebar and polish.

## Recommended Initial File Targets

### Backend

- `backend/src/gateway/routers/documents.py`
- `backend/src/gateway/application.py`
- `backend/src/documents/`

### Frontend

- `frontend/src/app/workspace/docs/[doc_id]/page.tsx`
- `frontend/src/components/workspace/block-editor/`
- `frontend/src/core/documents/`
- `frontend/src/components/workspace/doc-edit-dialog.tsx`
- `frontend/src/components/workspace/artifacts/artifact-file-detail.tsx`

## Open Questions

1. Should document drafts be local-only or first-class workspace objects visible in navigation from day one?
2. Should selecting a winner auto-create a document, or should the user explicitly click “Open in Editor”?
3. Do we want comments/annotations in the first editor release, or only editing plus AI transforms?
4. Should SurfSense export happen only from finalized markdown, or from saved document drafts as well?

## Recommendation

Approve this as a staged implementation, then build through Phase 2 before evaluating whether block-level AI actions need deeper backend graph integration.

That path gives MaestroFlow the value of a Notion-style editor without destabilizing the current doc-edit orchestration model.
