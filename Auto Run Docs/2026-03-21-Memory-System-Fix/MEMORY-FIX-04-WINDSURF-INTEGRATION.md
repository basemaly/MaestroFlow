# Phase 4: Configure Windsurf for Shared-Context & Mengram

## Objective
Create `.windsurfrules` file that instructs Windsurf to load Shared-Context and Mengram memory on startup, enabling context-aware coding in Windsurf sessions.

---

- [ ] **Create `.windsurfrules` file in workspace root**

Create: `/Volumes/BA/DEV/.windsurfrules`

```markdown
# Windsurf Rules — Shared-Context & Mengram Memory Integration

You are an AI coding assistant operating in a multi-IDE shared-memory environment.

## Memory System Setup

This workspace uses two integrated memory systems:

1. **Shared-Context Vault** (`/Volumes/BA/DEV/Shared-Context/`)
   - Human-auditable source of truth for architecture, decisions, project state
   - Git-synced every 15 min via launchd (`mv-sync` command)
   - Tiered access: Hot (WORKSPACE.md, ARCHITECTURE.md, DECISIONS.md) → Warm (SYSTEM/) → Cold (archives)

2. **Mengram Semantic Memory** (MCP-backed)
   - Durable facts, preferences, procedures, project summaries
   - Call `search_memory(query)` at session start with current task
   - Use `add_memories(items)` to save any user decisions or technical context worth retaining

## Session Startup Protocol

**PRIORITY ONE — Load Context First:**

1. Identify the current project (from user message or working directory)
2. Call `search_memory(query="{project_name} {task_type}")` to load relevant facts
3. For known projects: Read `/Volumes/BA/DEV/Shared-Context/WORKSPACES/{project}/WORKSPACE.md`
4. Then read: `ARCHITECTURE.md` (tech stack, structure, naming)
5. Then read: `DECISIONS.md` (past decisions, rationale, lessons learned)
6. Use retrieved context to inform all code changes and recommendations

**Example (StateWeave project):**
```
User: "Help me debug the state persistence layer"
↓
[Agent] Call: search_memory("StateWeave persistence layer architecture")
↓
[Agent] Read: /Volumes/BA/DEV/Shared-Context/WORKSPACES/StateWeave/WORKSPACE.md
↓
[Agent] Read: ARCHITECTURE.md (data structure, storage strategy)
↓
[Agent] Read: DECISIONS.md (why this storage choice, known issues)
↓
[Agent] → Respond with full architectural context
```

## Context Retrieval Tiers

**Hot Context (Always Load):**
- `WORKSPACE.md` — Project status, active goals, high-priority issues
- `ARCHITECTURE.md` — System design, component structure, tech choices
- `DECISIONS.md` — Major decisions with justification (prevents repeated mistakes)

**Warm Context (Load When Task Touches This Area):**
- `/Shared-Context/SYSTEM/Context-Tiers.md` — Tier-based retrieval strategy
- `/Shared-Context/SYSTEM/Agent-Startup-Protocol.md` — Multi-agent workflow

**Cold Context (On-Demand):**
- Long-form specs, archived decisions, old experiments
- Request from user: "Show me how we tried this before"

## Code Quality Commitments

- **Before writing any code:** Search memory for existing implementations, design patterns, prior decisions
- **Use established patterns:** Refer to ARCHITECTURE.md conventions; don't invent new ones
- **Document decisions:** If your change affects future work, save it to memory:
  ```
  add_memories([{
    type: "decision",
    entity: "StateWeave",
    content: "Chose immutable state updates over mutation to prevent race conditions in concurrent writes"
  }])
  ```
- **Reference memory facts in code:** Include comments: "Per ARCHITECTURE.md, this module handles..."

## Cross-IDE Collaboration

All agents (OpenCode, Claude Code, Cursor, Windsurf, Gemini) share:
- Same Shared-Context vault (git-synced)
- Same Mengram memory backend (MCP-connected)
- Same project conventions and decisions

**If work spans IDEs:**
```
Windsurf: search_memory("feature X implementation status")
→ Retrieve: "OpenCode started feature X in PR #42, blocked on API design"
→ Continue from there; don't restart analysis
```

**Handoff pattern:**
- Before switching IDEs, update WORKSPACE.md with current progress
- Save session summary to Mengram: `add_memories([{type: "handoff", entity: "ProjectName", content: "..."}])`
- Next IDE loads same context and continues seamlessly

## Key File Locations

- **Workspace root:** `/Volumes/BA/DEV`
- **Shared-Context vault:** `/Volumes/BA/DEV/Shared-Context/` (git-backed, read-only for agents)
- **Auto Run playbooks:** `/Volumes/BA/DEV/Auto Run Docs/` (multi-phase automation)
- **Project workspaces:** `/Volumes/BA/DEV/WORKSPACES/{ProjectName}/` (writable)

## Available Tools

- `read` — Access vault files and documentation
- `mengram_recall`, `mengram_search`, `mengram_search_all` — Query memory across types
- `mengram_remember`, `mengram_checkpoint` — Save facts, decisions, sessions
- `bash` — Git, npm, docker, env commands (run in project root)
- `jcodemunch_*`, `CodeGraphContext_*` — Code indexing and analysis

## Rules of Engagement

- **Always read before writing** — Search memory and vault for context
- **Explicit over implicit** — If assumptions exist, verify in DECISIONS.md
- **Memory is source of truth** — If memory contradicts code, investigate and update memory
- **Ask before modifying vault** — Rare, but if you need to edit ARCHITECTURE.md or DECISIONS.md, confirm with user first
- **Document ambiguity** — If a design choice is unclear, add a decision record in Mengram

## When to Escalate

- Cross-project decisions → Search memory to check dependencies
- Contradictions between code and docs → Update DECISIONS.md to resolve
- New architectural direction → Add decision to memory and notify other IDEs

---

**Initialization Status:** Memory systems active. Load project context on every session start.
```

**Verify file created:**
```bash
ls -la /Volumes/BA/DEV/.windsurfrules
wc -l /Volumes/BA/DEV/.windsurfrules  # Should be ~120+ lines
```

---

- [ ] **Test Windsurf reads the .windsurfrules file**

Open Windsurf, create a new workspace in `/Volumes/BA/DEV`, and:
1. Ask: "What memory systems are available in this workspace?"
2. Windsurf should cite `.windsurfrules` and describe Shared-Context + Mengram
3. Windsurf should mention hot/warm/cold context tiers

**Expected response:**
- References to `.windsurfrules` file
- Understanding of Shared-Context Vault and Mengram
- Knowledge of tier-based retrieval

---

- [ ] **Verify Windsurf can access the memory system**

In Windsurf terminal:
```bash
cd /Volumes/BA/DEV
ls Shared-Context/WORKSPACES/ | head -10
```

Should list project directories without errors.

---

- [ ] **Test startup protocol with a real project query**

In Windsurf, ask:
```
I'm starting work on Maestro.app. Load the project context and tell me the current architecture.
```

Windsurf should:
1. Search memory for "Maestro.app architecture"
2. Read `/Volumes/BA/DEV/Shared-Context/WORKSPACES/Maestro.app/WORKSPACE.md` (or similar)
3. Read ARCHITECTURE.md and DECISIONS.md
4. Provide full context with specific technical details

**Expected indicators:**
- Mentions tech stack, APIs, component structure
- References past decisions and lessons learned
- Shows understanding of project state

---

- [ ] **Verify Windsurf honors context tiers**

Ask Windsurf:
```
I need deep historical context about why we chose this tech stack. Show me the decision rationale.
```

Windsurf should:
1. Read DECISIONS.md (warm context)
2. Find and cite the relevant decision record
3. Explain the "why" behind the choice

---

## Success Criteria
- [ ] `.windsurfrules` file exists at `/Volumes/BA/DEV/.windsurfrules`
- [ ] Windsurf auto-discovers and reads `.windsurfrules`
- [ ] Windsurf mentions Shared-Context and Mengram on first prompt
- [ ] Windsurf can access `/Volumes/BA/DEV` and list projects
- [ ] Sample project query returns architecture + decisions context
- [ ] Windsurf applies context tiers (hot → warm → cold)
- [ ] Windsurf doesn't ask "how do I access memory?" on second session

## Notes
- `.windsurfrules` is auto-discovered by Windsurf in workspace root
- Works identically to `.cursorrules` — same pattern, different file
- Both files can coexist; each IDE reads its own rules file
- Changes take effect on next IDE session
- If Windsurf ignores the file, verify it's in the workspace root directory
