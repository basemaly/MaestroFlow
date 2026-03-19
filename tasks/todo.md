# Documents Composer Desk Plan

## Goal

Extend MaestroFlow Documents with low-risk saved quick actions and writing memory, plus medium-scope document snapshots with diff and restore, while keeping the workflow closer to a composer's collage desk than a sterile settings panel.

## Plan

- [x] Read current Documents storage, editor shell, and related workspace surfaces
- [x] Add document-native persistence for writing memory, quick actions, and snapshots
- [x] Extend the Documents API and transform path to use writing memory during edits
- [x] Integrate desk-card quick actions, writing memory, and snapshot diff/restore into the block editor shell
- [x] Add targeted backend tests for quick actions, writing memory, and snapshots
- [x] Run backend tests, frontend typecheck, and targeted eslint on changed files

## Review

- Writing memory is document-native rather than reused from the broader chat memory system, so editing stays predictable and scoped to the draft.
- Quick actions are saved as reusable desk cards for one-click transforms instead of expanding the built-in operation enum further.
- Snapshots are explicit saves with diff and restore, and restore automatically creates a pre-restore backup snapshot before overwriting the draft.
