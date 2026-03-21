# Phase 3: Configure Cursor for Shared-Context & Mengram

## Objective
Create `.cursorrules` file that instructs Cursor to load Shared-Context and Mengram memory on startup, enabling context-aware coding in Cursor sessions.

---

- [ ] **Create `.cursorrules` file in workspace root**

Create: `/Volumes/BA/DEV/.cursorrules`

```markdown
# Cursor Rules — Shared-Context & Mengram Memory Integration

You are an AI coding assistant operating in a multi-IDE shared-memory environment.

## Memory System Setup

This workspace uses two integrated memory systems:

1. **Shared-Context Vault** (`/Volumes/BA/DEV/Shared-Context/`)
   - Human-auditable source of truth for architecture, decisions, project state
   - Git-synced every 15 min via launchd
   - Tiered access: Hot (WORKSPACE.md, ARCHITECTURE.md, DECISIONS.md) → Warm (SYSTEM/) → Cold (archives)

2. **Mengram Semantic Memory** (MCP-backed)
   - Durable facts, preferences, procedures, project summaries
   - Call `search_memory(query)` at session start with current task
   - Use `add_memories(items)` to save any user decisions, preferences, or technical context

## Session Startup Protocol

**ALWAYS DO THIS FIRST:**

1. Identify the current project (from user message or pwd)
2. Call `search_memory(query="{project_name} architecture setup")` to load project facts
3. If known project: Read `/Volumes/BA/DEV/Shared-Context/WORKSPACES/{project}/WORKSPACE.md`
4. Then read: `ARCHITECTURE.md`, then `DECISIONS.md` (in order)
5. Use retrieved context to inform all code changes

**Example startup (MaestroFlow project):**
```
User: "Help me fix the MaestroFlow deployment bug"
↓
[Agent] Call: search_memory("MaestroFlow deployment architecture")
↓
[Agent] Read: /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/WORKSPACE.md
↓
[Agent] Read: ARCHITECTURE.md (tech stack, API structure)
↓
[Agent] Read: DECISIONS.md (past bug fixes, deployment lessons)
↓
[Agent] → Now respond with full context
```

## Context Tiers

**Hot (Load Always):**
- `WORKSPACE.md` — Project summary, active state, promoted context
- `ARCHITECTURE.md` — Stable structure, tech stack, naming conventions
- `DECISIONS.md` — Major decisions with rationale (prevents repeating mistakes)

**Warm (Load If Touching That Area):**
- `/Shared-Context/SYSTEM/Context-Tiers.md` — How to use tiered retrieval
- `/Shared-Context/SYSTEM/Agent-Startup-Protocol.md` — Cross-agent workflow rules

**Cold (Load On Demand):**
- Deeper project notes, old specs, archives
- Request from user: "Tell me about past attempts to solve X"

## Code Quality Standards

- **Before writing code:** Search memory for existing implementations, established patterns, prior decisions
- **After writing code:** Save decision to memory if it resolves ambiguity or affects future changes
  ```
  add_memories([{
    type: "decision",
    entity: "MaestroFlow",
    content: "Chose PostgreSQL over SQLite for connection pooling in production"
  }])
  ```
- **Use established patterns** from ARCHITECTURE.md over creating new conventions
- **Reference memory facts** in your response: "Per MaestroFlow ARCHITECTURE.md, the API uses..."

## Multi-IDE Coordination

When work spans multiple IDEs (OpenCode, Claude Code, Cursor, Windsurf, Gemini):
- All agents read same Shared-Context vault
- All agents write to same Mengram memory
- Use `procedure_id` to resume work started in another IDE

Example: If OpenCode started fixing bug #42:
```
Claude Code: search_memory("bug 42 fix status")
→ Retrieve: "Cursor analyzed issue, found root cause in auth.ts:145"
→ Continue from there, don't restart analysis
```

## Handoff Between Sessions

When ending a session or passing work to another agent:
1. Update relevant `WORKSPACE.md` or `DECISIONS.md`
2. Call `add_memories()` with session summary:
   ```
   add_memories([{
     type: "handoff",
     entity: "ProjectName",
     content: "Completed X, next step is Y. See commit abc1234."
   }])
   ```
3. Commit Shared-Context changes if you touched vault files

## Key Directories

- **Project root:** `/Volumes/BA/DEV`
- **Shared-Context vault:** `/Volumes/BA/DEV/Shared-Context/` (read-only for code agents)
- **Auto Run docs:** `/Volumes/BA/DEV/Auto Run Docs/` (shared playbooks)
- **Individual projects:** `/Volumes/BA/DEV/WORKSPACE/{ProjectName}/` (writable)

## Tools Available

- `read` — Read vault files and project docs
- `mengram_recall`, `mengram_search` — Query memory
- `mengram_remember` — Save facts and decisions
- `jcodemunch_search_symbols`, `CodeGraphContext_*` — Code indexing (read-only)
- `bash` — Git, npm, docker, etc. (prefer in your project workspace)

## When to Ask for Help

- If a task requires decisions outside the current project scope → search memory first
- If context conflicts with memory → update DECISIONS.md to resolve
- If you need to modify Shared-Context (rare) → ask user before committing

---

**Status:** Memory system active. Ready to load project context on every session.
```

**Verify file created:**
```bash
ls -la /Volumes/BA/DEV/.cursorrules
wc -l /Volumes/BA/DEV/.cursorrules  # Should be ~120+ lines
```

---

- [ ] **Test Cursor reads the .cursorrules file**

Open Cursor, create a new tab, navigate to `/Volumes/BA/DEV`, and:
1. Open any project (e.g., MaestroFlow)
2. Ask: "What are the startup protocols and context tiers for this workspace?"
3. Cursor should cite `.cursorrules` content and understand the memory system

**Expected response:**
- Cursor mentions "Shared-Context Vault", "Hot/Warm/Cold tiers"
- Cursor is aware of Mengram memory system
- Cursor knows to call `search_memory()` on session start

---

- [ ] **Verify Cursor can access Mengram memory**

In Cursor, run this command in the terminal (or ask Cursor to run it):
```bash
cd /Volumes/BA/DEV
# Cursor should be able to see this path and read files
ls -la Shared-Context/WORKSPACES/ | head -10
```

Cursor should output project list without errors.

---

- [ ] **Test startup protocol with a sample query**

In Cursor, ask:
```
I'm working on MaestroFlow. Summarize the architecture and recent decisions.
```

Cursor should:
1. Recognize "MaestroFlow" as a project
2. Search memory for "MaestroFlow architecture"
3. Read `/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/ARCHITECTURE.md`
4. Read `DECISIONS.md`
5. Provide context-aware response

**Expected output:**
- References to specific architecture decisions
- Mentions of tech stack, API design, past bug fixes
- Shows work from vault files

---

## Success Criteria
- [ ] `.cursorrules` file exists at `/Volumes/BA/DEV/.cursorrules`
- [ ] Cursor reads and acknowledges `.cursorrules` content
- [ ] Cursor knows about Shared-Context and Mengram on first prompt
- [ ] Cursor can access project directory (`/Volumes/BA/DEV`)
- [ ] Sample query returns context from ARCHITECTURE.md or DECISIONS.md
- [ ] Cursor doesn't ask "what's my memory system?" on new projects

## Notes
- `.cursorrules` is auto-discovered by Cursor in repo root
- Changes to `.cursorrules` take effect on next Cursor session
- Cursor will follow these rules by default (no additional config needed)
- If Cursor ignores rules, check: is `.cursorrules` in the workspace root?
