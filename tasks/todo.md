# Notion-Style Block Editor Plan

## Goal

Add a staged, Tiptap-based block editor to MaestroFlow that complements the existing doc-edit workflow instead of replacing it.

## Plan

- [x] Read project context, architecture, and decisions
- [x] Inspect current doc-edit frontend and backend surfaces
- [x] Create working branch `codex/notion`
- [x] Write detailed implementation plan in `docs/notion-block-editor-implementation-plan.md`
- [x] Record execution checklist in `tasks/todo.md`
- [ ] Get plan approval or adjustments from user
- [ ] Implement Phase 1 document API and persistence
- [ ] Implement Phase 1 editor shell and markdown conversion
- [ ] Implement document route and save/load flow
- [ ] Integrate selected doc-edit winners into editor flow
- [ ] Integrate markdown artifact handoff into editor flow
- [ ] Implement block-level AI transforms
- [ ] Add tests and end-to-end verification

## Review

- The plan preserves the current supervised doc-edit workflow.
- The plan keeps markdown as canonical in Phase 1 to reduce migration risk.
- The plan separates document CRUD from doc-edit orchestration to keep API boundaries clean.
