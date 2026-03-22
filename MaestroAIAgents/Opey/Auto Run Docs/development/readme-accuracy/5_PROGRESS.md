# README Accuracy Gate - Feature Coverage Target

## Context
- **Playbook:** Usage
- **Agent:** Mozart
- **Project:** /Volumes/BA/DEV/MaestroAIAgents/Mozart
- **Auto Run Folder:** /Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs
- **Loop:** 00001

## Purpose

This document is the **accuracy gate** for the usage documentation pipeline. It checks whether all major user-facing features are accurately documented in the README. **This is the only document with Reset ON** - it controls loop continuation by resetting tasks in documents 1-4 when more work is needed.

## Instructions

1. **Read the plan** from `/Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs/LOOP_00001_PLAN.md`
2. **Check for remaining `PENDING` items** with CRITICAL/HIGH importance and EASY/MEDIUM effort
3. **If such PENDING items exist**: Reset all tasks in documents 1-4 to continue the loop
4. **If NO such items exist**: Do NOT reset - pipeline exits (README is accurate)

## Accuracy Gate Check

- [x] **Check for remaining gaps**: Read LOOP_00001_PLAN.md and check if there are any items with status `PENDING` that have CRITICAL or HIGH user importance AND EASY or MEDIUM fix effort. If such items exist, reset documents 1-4 to continue the loop. If no auto-fixable high-importance gaps remain, do NOT reset anything - allow the pipeline to exit.
  - ✅ **Result:** All 10 PENDING items with CRITICAL/HIGH importance and EASY/MEDIUM effort are already IMPLEMENTED (DOC-001 through DOC-010)
  - ✅ **Only remaining PENDING item:** DOC-011 (NEEDS REVIEW - requires maintainer decision, not auto-fixable)
  - ✅ **Deferred items:** DOC-012, DOC-013, DOC-014 are intentionally WON'T DO
  - ✅ **Decision:** NO RESET REQUIRED - Pipeline should EXIT
  - **Verified:** 2026-03-21 - LOOP_00001_PLAN.md confirms all auto-fixable gaps are IMPLEMENTED

## Reset Tasks (Only if PENDING high-importance gaps exist)

If the accuracy gate check above determines we need to continue, reset all tasks in the following documents:

- [ ] **Reset 1_ANALYZE.md**: Uncheck all tasks in `/Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs/1_ANALYZE.md`
- [ ] **Reset 2_FIND_GAPS.md**: Uncheck all tasks in `/Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs/2_FIND_GAPS.md`
- [ ] **Reset 3_EVALUATE.md**: Uncheck all tasks in `/Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs/3_EVALUATE.md`
- [ ] **Reset 4_IMPLEMENT.md**: Uncheck all tasks in `/Volumes/BA/DEV/MaestroAIAgents/Opey/Auto Run Docs/4_IMPLEMENT.md`

**IMPORTANT**: Only reset documents 1-4 if there are PENDING items with CRITICAL/HIGH importance and EASY/MEDIUM effort. If all such items are IMPLEMENTED, or only HARD effort items remain, leave these reset tasks unchecked to allow the pipeline to exit.

## Decision Logic

```
IF LOOP_00001_PLAN.md doesn't exist:
    → Do NOT reset anything (PIPELINE JUST STARTED - LET IT RUN)

ELSE IF no PENDING items with (CRITICAL|HIGH importance) AND (EASY|MEDIUM effort):
    → Do NOT reset anything (README IS ACCURATE - EXIT)

ELSE:
    → Reset documents 1-4 (CONTINUE TO NEXT LOOP)
```

## How This Works

This document controls loop continuation through resets:
- **Reset tasks checked** → Documents 1-4 get reset → Loop continues
- **Reset tasks unchecked** → Nothing gets reset → Pipeline exits

### Exit Conditions (Do NOT Reset)

1. **All Fixed**: All CRITICAL/HIGH importance gaps are `IMPLEMENTED`
2. **All Skipped**: Remaining gaps are `WON'T DO` (intentionally undocumented)
3. **Only Hard Items**: Remaining gaps need `NEEDS REVIEW` (HARD effort)
4. **Only Low Priority**: Remaining gaps are MEDIUM/LOW importance
5. **Max Loops**: Hit the loop limit in Batch Runner

### Continue Conditions (Reset Documents 1-4)

1. There are `PENDING` items with CRITICAL or HIGH user importance
2. Those items have EASY or MEDIUM fix effort
3. We haven't hit max loops

## Current Status

Before making a decision, check the plan file:

| Metric | Value |
|--------|-------|
| **PENDING (CRITICAL/HIGH, EASY/MEDIUM)** | 0 (all 10 IMPLEMENTED) |
| **PENDING (other)** | 1 (DOC-011 NEEDS REVIEW) |
| **IMPLEMENTED** | 10 |
| **WON'T DO** | 3 |
| **NEEDS REVIEW** | 1 |

## Accuracy Estimate

| Category | Count |
|----------|-------|
| **Features in code** | ___ |
| **Features documented** | ___ |
| **Stale docs removed** | ___ |
| **Estimated accuracy** | ___ % |

## Progress History

Track progress across loops:

| Loop | Gaps Fixed | Gaps Remaining | Decision |
|------|------------|----------------|----------|
| 1 | 10 | 4 (1 NEEDS_REVIEW + 3 WON'T_DO) | EXIT |

## Manual Override

**To force exit early:**
- Leave all reset tasks unchecked regardless of PENDING items

**To continue fixing MEDIUM importance gaps:**
- Check the reset tasks even when no CRITICAL/HIGH remain

**To pause for maintainer review:**
- Leave unchecked
- Review USAGE_LOG and plan file
- Address NEEDS REVIEW items manually
- Restart when ready

## Remaining Work Summary

Items that still need attention after this loop:

### Needs Maintainer Review
- [ ] **DOC-011: Fallback URL Support** - Requires clarification on configuration method (env vars, config file, or programmatic), fallback activation logic (circuit open, timeout, or both), and whether per-service examples are needed.

### Intentionally Undocumented
- [ ] **DOC-012: SurfSense Integration Pattern** - Service-specific integration pattern, to be documented in advanced/integration-patterns.md
- [ ] **DOC-013: LiteLLM Cost Protection Pattern** - Service-specific tuning example, can be in advanced docs or custom services guide
- [ ] **DOC-014: Per-Service Health Checks** - Optional advanced monitoring feature, document in monitoring.md as enhancement

### Low Priority (future)
- (None identified in this loop)

## Notes

- The goal is an **accurate README** that matches actual features
- Not every internal detail needs documentation
- Some features may be intentionally undocumented (internal use)
- Stale documentation (removed features) is as bad as missing docs
- Quality matters - accurate descriptions over comprehensive coverage
