# MaestroFlow Handoff Manifest

This is the human-readable companion to [maestroflow-handoff-manifest.json](/Volumes/BA/DEV/MaestroFlow/docs/maestroflow-handoff-manifest.json).

## Closest Thing To A Comprehensive Manual

These are the best starting documents if another agent needs to understand MaestroFlow quickly and comprehensively.

1. [README.md](/Volumes/BA/DEV/MaestroFlow/README.md)  
   Best public-facing overview of what MaestroFlow is.
2. [backend/docs/README.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/README.md)  
   Closest thing to a backend/operator manual.
3. [ARCHITECTURE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/ARCHITECTURE.md)  
   Highest-signal description of the intended system architecture.
4. [DECISIONS.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/DECISIONS.md)  
   Running record of major product, infrastructure, UI, and workflow decisions.
5. [WORKSPACE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/WORKSPACE.md)  
   Human-oriented project summary and orientation document.

## Critical

- [README.md](/Volumes/BA/DEV/MaestroFlow/README.md)  
  Best public-facing overview of what MaestroFlow is.
- [backend/docs/README.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/README.md)  
  Closest thing to a backend/operator manual.
- [ARCHITECTURE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/ARCHITECTURE.md)  
  Highest-signal description of the intended system architecture.
- [DECISIONS.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/DECISIONS.md)  
  Running record of major product, infrastructure, UI, and workflow decisions.

## High Priority

- [WORKSPACE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/WORKSPACE.md)  
  Human-oriented project summary and orientation document.
- [backend/docs/ARCHITECTURE.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/ARCHITECTURE.md)  
  Backend-specific architecture, components, and integration details.
- [backend/docs/API.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/API.md)  
  Main backend API reference for gateway and app integrations.
- [backend/docs/CONFIGURATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/CONFIGURATION.md)  
  Best reference for environment variables and runtime config behavior.
- [backend/docs/SETUP.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/SETUP.md)  
  Primary backend setup and local development guide.
- [backend/docs/LANGGRAPH_STORAGE_MIGRATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/LANGGRAPH_STORAGE_MIGRATION.md)  
  Explains the LangGraph storage split, migration logic, and compatibility layer.
- [PLANNING-STEERING-SPEC.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/PLANNING-STEERING-SPEC.md)  
  Defines planning and steering behavior that affects Executive and workflow orchestration.
- [CALIBRE_INTEGRATION_REVIEW.md](/Volumes/BA/DEV/MaestroFlow/CALIBRE_INTEGRATION_REVIEW.md)  
  Tracks Calibre integration tradeoffs and architecture decisions.
- [CALIBRE-SERVER-INGEST-PLAN.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/CALIBRE-SERVER-INGEST-PLAN.md)  
  Companion planning doc for the Calibre ingest and retrieval direction.
- [notion-block-editor-implementation-plan.md](/Volumes/BA/DEV/MaestroFlow/docs/notion-block-editor-implementation-plan.md)  
  Best design and implementation plan for the document editor and Revision Lab evolution.

## Medium Priority

- [about.md](/Volumes/BA/DEV/MaestroFlow/frontend/src/components/workspace/settings/about.md)  
  In-app product/about copy that reflects current product framing.
- [LITELLM_BOTTLENECK_FIXES.md](/Volumes/BA/DEV/MaestroFlow/LITELLM_BOTTLENECK_FIXES.md)  
  Background for LiteLLM, model path cleanup, and performance tuning.
- [CODE_CHANGE_SUMMARY_BY_FILE.md](/Volumes/BA/DEV/MaestroFlow/docs/CODE_CHANGE_SUMMARY_BY_FILE.md)  
  Helpful file-by-file summary of a major implementation slice.
- [MAESTROFLOW_AIO_SANDBOX.md](/Volumes/BA/DEV/MaestroFlow/docs/MAESTROFLOW_AIO_SANDBOX.md)  
  Documents sandbox/runtime behavior and Apple container support direction.
- [MCP_SERVER.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/MCP_SERVER.md)  
  Describes MCP server integration and related operational behavior.
- [FILE_UPLOAD.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/FILE_UPLOAD.md)  
  Explains file upload and conversion behavior, relevant to documents and workflows.
- [MEMORY_IMPROVEMENTS.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/MEMORY_IMPROVEMENTS.md)  
  Longer-form design notes on memory behavior and planned improvements.
- [MEMORY_IMPROVEMENTS_SUMMARY.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/MEMORY_IMPROVEMENTS_SUMMARY.md)  
  Shorter summary of the memory-improvement direction.
- [plan_mode_usage.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/plan_mode_usage.md)  
  Documents plan mode behavior, which matters for planning and Executive flows.
- [task_tool_improvements.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/task_tool_improvements.md)  
  Important history for task tool and subagent orchestration evolution.
- [summarization.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/summarization.md)  
  Covers summarization behavior that affects chat and memory quality.
- [AUTO_TITLE_GENERATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/AUTO_TITLE_GENERATION.md)  
  Explains automatic thread-title generation behavior.
- [TITLE_GENERATION_IMPLEMENTATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/TITLE_GENERATION_IMPLEMENTATION.md)  
  Implementation detail for title generation logic.
- [CONTRIBUTING.md](/Volumes/BA/DEV/MaestroFlow/CONTRIBUTING.md)  
  Contribution and development workflow reference.
- [SECURITY.md](/Volumes/BA/DEV/MaestroFlow/SECURITY.md)  
  Security posture and reporting reference.
- [AGENTS.md](/Volumes/BA/DEV/MaestroFlow/AGENTS.md)  
  Local repo-specific operating instructions for agents.
- [CLAUDE.md](/Volumes/BA/DEV/MaestroFlow/CLAUDE.md)  
  Additional repo guidance and conventions.
- [AGENT-GUIDE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/_SYSTEM/AGENT-GUIDE.md)  
  System guide for shared context, memory, and cross-project operating rules.

## Low Priority But Potentially Useful

- [tasks/todo.md](/Volumes/BA/DEV/MaestroFlow/tasks/todo.md)  
  Residual task list that may still contain relevant unfinished work.
- [docs/052d5390/run-report.md](/Volumes/BA/DEV/MaestroFlow/docs/052d5390/run-report.md)  
  Representative run report for the editorial and revision workflow.
- [docs/5f9614aa/run-report.md](/Volumes/BA/DEV/MaestroFlow/docs/5f9614aa/run-report.md)  
  Representative run report including humanizer and critic-loop passes.
- [docs/ae7b6e00/run-report.md](/Volumes/BA/DEV/MaestroFlow/docs/ae7b6e00/run-report.md)  
  Representative run report including writing-refiner, argument-critic, and humanizer outputs.

## Feature-Surface Skill Docs

These are not general manuals, but they document workflows now exposed through MaestroFlow’s skill surface.

- [humanizer/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/humanizer/SKILL.md)
- [humanize-writing/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/humanize-writing/SKILL.md)
- [rhetoric-annotation/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/rhetoric-annotation/SKILL.md)
- [persuade-critique/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/persuade-critique/SKILL.md)
- [self-critique-refinement/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/self-critique-refinement/SKILL.md)
- [prompt-engineering-playbook/SKILL.md](/Volumes/BA/DEV/MaestroFlow/skills/public/prompt-engineering-playbook/SKILL.md)

## Suggested Reading Order For A Separate Agent

1. [README.md](/Volumes/BA/DEV/MaestroFlow/README.md)
2. [backend/docs/README.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/README.md)
3. [ARCHITECTURE.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/ARCHITECTURE.md)
4. [DECISIONS.md](/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/DECISIONS.md)
5. [backend/docs/ARCHITECTURE.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/ARCHITECTURE.md)
6. [backend/docs/API.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/API.md)
7. [backend/docs/CONFIGURATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/CONFIGURATION.md)
8. [backend/docs/LANGGRAPH_STORAGE_MIGRATION.md](/Volumes/BA/DEV/MaestroFlow/backend/docs/LANGGRAPH_STORAGE_MIGRATION.md)
9. [notion-block-editor-implementation-plan.md](/Volumes/BA/DEV/MaestroFlow/docs/notion-block-editor-implementation-plan.md)
10. [CALIBRE_INTEGRATION_REVIEW.md](/Volumes/BA/DEV/MaestroFlow/CALIBRE_INTEGRATION_REVIEW.md)
