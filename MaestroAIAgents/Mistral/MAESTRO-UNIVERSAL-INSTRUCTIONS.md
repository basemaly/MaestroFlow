# MaestroAIAgents — Universal Agent Instructions

**Location:** Project root (`/Volumes/BA/DEV/MaestroAIAgents/Mistral/`)  
**Scope:** Claude Code, Cursor, Windsurf, Gemini  
**Updated:** 2026-03-21  
**Status:** All 6 phases complete; production-ready

---

## Quick Start (Every Session)

### Step 1: Load Context (2 min)
```bash
# Read project overview (this file)
# Then read Shared-Context workspace:
cat /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/WORKSPACE.md

# Query memory for session history:
mengram_search("MaestroAIAgents")
```

### Step 2: Understand Architecture (3 min)
Read `/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/ARCHITECTURE.md` — covers:
- 6 completed integration phases
- Mengram memory + Shared-Context vault
- 4 IDEs (Claude Code, Cursor, Windsurf, Gemini) all integrated
- Hot/warm/cold context tier model

### Step 3: Check Recent Work
```bash
cd /Volumes/BA/DEV/MaestroAIAgents/Mistral
git log --oneline -10  # See Phase 1-6 commits
```

### Step 4: Begin Task
- If continuing prior work: query Mengram for procedures + learnings
- If starting new work: read DECISIONS.md for design philosophy

---

## Project Structure

```
/Volumes/BA/DEV/MaestroAIAgents/Mistral/
├── MAESTROFLOW-DB-POOLING-REVIEW.md      [Database optimization work]
├── MAESTROFLOW-DB-POOLING-QUICKSTART.sh  [DB deployment script]
├── .logs/                                  [Phase execution logs]
├── .git/                                   [6 completed phases in history]
└── /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/
    ├── WORKSPACE.md                        [Project overview + quick start]
    ├── ARCHITECTURE.md                     [System design + 6 phases]
    └── DECISIONS.md                        [Design rationale + tradeoffs]
```

---

## What This Project Does

**Goal:** Create universal memory and IDE integration for AI agents working across `/Volumes/BA/DEV` workspace ecosystem.

**Core Achievement:** 4 IDEs (Claude Code, Cursor, Windsurf, Gemini) all use the same memory backend (Mengram) and share facts, procedures, decisions across sessions.

**Key Systems:**
- **Mengram:** Cloud-backed memory; semantic search; procedure tracking
- **Shared-Context vault:** Git-backed project documentation; ARCHITECTURE.md + DECISIONS.md live here
- **IDE rules:** `.cursorrules`, `.windsurfrules` auto-load context at session start
- **Phase log:** 6 completed phases documented in git commits (each commit has detailed body)

---

## Critical Paths by Task

### If Starting Work on a Known Project
1. **Load hot context:** IDE rules auto-load (if `.cursorrules` / `.windsurfrules` exist in project)
2. **Load warm context:** Read ARCHITECTURE.md + DECISIONS.md from Shared-Context vault
3. **Query memory:** `mengram_search("project-name")`  — retrieves procedures + learnings from prior sessions
4. **Begin work:** You now have full project context

### If Debugging a Failing Phase
1. **Check git log:** `git log --format="%h %s %b"` — phase bodies explain what was done
2. **Read DECISIONS.md:** Section "Decision X" explains why each phase was designed that way
3. **Query Mengram:** `mengram_search("MaestroAIAgents phase <N>")` — retrieves learnings from that phase
4. **Check cold context:** `.logs/subtask2.log` has detailed phase execution logs

### If Adding a New IDE or Phase
1. **Read ARCHITECTURE.md:** Understand phased integration approach
2. **Read DECISIONS.md Decision 5:** Explains why phases are sequential
3. **Copy existing IDE rules:** Use `.cursorrules` or `.windsurfrules` as template
4. **Add to phase log:** `git commit -m "MAESTRO: Phase N - <description>"` with detailed body
5. **Update Shared-Context:** Add learnings to WORKSPACE.md or DECISIONS.md
6. **Push to vault:** `cd /Volumes/BA/DEV/Shared-Context && git push`

### If Encountering Merge Conflicts in Shared-Context
1. **Check vault status:** `cd /Volumes/BA/DEV/Shared-Context && git status`
2. **Review remote:** `git diff origin/master HEAD`
3. **Prefer remote if unsure:** `git checkout --theirs <file> && git add . && git commit`
4. **Pull/push regularly:** Launchd syncs every 15 min; minimize window for conflicts

---

## Memory System: How It Works

### Mengram (Primary Memory)
**What:** Cloud-backed, searchable memory accessible from all 4 IDEs  
**Query:** `mengram_search("MaestroAIAgents")` → returns top 5 facts + procedures  
**Add:** `mengram_remember(conversation)` — extracts entities, facts, decisions from messages  
**Procedures:** `mengram_list_procedures()` — shows learned workflows from prior sessions

**Example:**
```bash
# In any IDE, query memory for prior work
mengram_search("MaestroAIAgents phase 3")

# Result: {
#   facts: [
#     "Phase 3: Created .cursorrules with 124 lines of hot context",
#     "Cursor integration auto-loads rules on startup"
#   ],
#   procedures: [
#     "Verify IDE rules load: Check for .cursorrules in project root"
#   ]
# }
```

### Shared-Context Vault (Durable)
**What:** Git-backed project documentation at `/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/`  
**Files:**
- `WORKSPACE.md` — Project overview, quick start, key files
- `ARCHITECTURE.md` — 6 phases, system design, tier model
- `DECISIONS.md` — Design rationale, tradeoffs, future work

**Auto-sync:** Launchd runs `git pull` every 15 min + `git push` on commit  
**Offline fallback:** If Mengram is down, read Shared-Context files from disk

**Example:**
```bash
# Read project architecture
cat /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/ARCHITECTURE.md

# Check if need to update vault
cd /Volumes/BA/DEV/Shared-Context && git status

# Make changes and push
echo "New fact" >> DECISIONS.md
git add . && git commit -m "docs: Add new decision" && git push
```

---

## IDE Integration Status

| IDE | Status | Rules | Memory | Auto-Load |
|-----|--------|-------|--------|-----------|
| **Claude Code** | ✅ Active | Native tools | Mengram + Vault MCP | Yes (built-in) |
| **Cursor** | ✅ Active | .cursorrules (124 lines) | Mengram | Yes (auto-discovers) |
| **Windsurf** | ✅ Active | .windsurfrules | Mengram | Yes (auto-discovers) |
| **Gemini** | ✅ Active | settings.json config | Mengram MCP | Yes (configured) |

**Verification:** Phase 6 confirmed all 4 IDEs share memory and respond to queries in < 500ms.

---

## Common Workflows

### Adding New Memory Facts
```bash
# From any IDE, after completing work:
mengram_remember([
  { role: "user", content: "What did you accomplish?" },
  { role: "assistant", content: "Created Cursor integration with .cursorrules..." }
])

# Or manually add facts:
mengram_add_memories([
  { entity: "MaestroAIAgents", fact: "Phase 3: .cursorrules auto-loads on startup", type: "decision" }
])
```

### Updating Shared-Context Documentation
```bash
# Read current workspace
cat /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/WORKSPACE.md

# Make edits (e.g., update WORKSPACE.md with new findings)
vim /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/WORKSPACE.md

# Commit and push
cd /Volumes/BA/DEV/Shared-Context
git add . && git commit -m "docs: Update MaestroAIAgents workspace - <reason>"
git push  # Launchd will also push if you forget
```

### Querying Memory for Task Help
```bash
# Before starting a task, search memory:
mengram_search("MaestroAIAgents <task-name>")

# Example: Before writing Phase 7:
mengram_search("MaestroAIAgents phase memory")
# Returns: procedures from Phases 1-6, learnings, known pitfalls
```

### Checking Phase History
```bash
# See all 6 phases with detailed messages
git log --format="%h %s %b"

# See Phase 3 specifically
git show bc3ed44  # Shows commit body with full Phase 3 description

# Search for specific phase
git log --grep="Phase 3"
```

---

## Context Tier Model

### **Hot** — Always Available (0 sec latency)
- `.cursorrules` / `.windsurfrules` (auto-loaded by IDE)
- IDE memory tools (`mengram_search`, `mengram_remember`)
- Recent git commits (`git log -5`)

**When to use:** Any session; assume this context is always present.

### **Warm** — Load at Task Start (30-60 sec)
- WORKSPACE.md (1 min read; overview + quick start)
- ARCHITECTURE.md (5 min read; understand system design)
- DECISIONS.md (3 min read; understand why decisions were made)
- Mengram semantic search: `mengram_search("MaestroAIAgents <task>")`

**When to use:** Beginning a task; before claiming you're ready to work.

### **Cold** — Load if Needed (2-5 min)
- Git logs (detailed phase bodies; `git show <commit>`)
- Phase documentation (`.logs/subtask2.log`, etc.)
- Shared-Context vault full history (`git log --oneline`)
- Related projects (MaestroFlow, LiteLLM, Surfsense)

**When to use:** Debugging; understanding edge cases; learning from similar prior work.

---

## Troubleshooting

### IDE Rules Not Loading
```bash
# Check .cursorrules exists
ls -la /Volumes/BA/DEV/MaestroAIAgents/Mistral/.cursorrules

# For Cursor: Open command palette → "Agent Instructions" → should show .cursorrules content
# For Windsurf: Same (--reveal agent rules in UI)
```

### Mengram Queries Timing Out
```bash
# Check Mengram processes running
ps aux | grep mengram

# If not running:
mengram start  # May require installation; check docs

# Test with simple query
mengram_search("test")
```

### Shared-Context Vault Not Syncing
```bash
# Check vault status
cd /Volumes/BA/DEV/Shared-Context && git status

# Manual pull/push if launchd misses
git pull origin master
git push origin master

# Check launchd job (if on macOS)
launchctl list | grep context
```

### Memory Corruption or Contradictions
```bash
# Run curator to detect contradictions + duplicates
mengram_run_agents(agent='curator')

# Run connector to build fresh relationship graph
mengram_run_agents(agent='connector')

# Check vault is clean
cd /Volumes/BA/DEV/Shared-Context && git log --oneline -5
```

---

## Key Documents (By Purpose)

| Purpose | Document | Location |
|---------|----------|----------|
| Quick start | This file + WORKSPACE.md | Project root + Shared-Context |
| System design | ARCHITECTURE.md | Shared-Context vault |
| Design rationale | DECISIONS.md | Shared-Context vault |
| Phase history | Git log (6 commits) | `.git/` |
| Database work | MAESTROFLOW-DB-POOLING-REVIEW.md | Project root |
| Detailed logs | .logs/subtask2.log | Cold context |

---

## Keeping Memory Clean

**Monthly (recommended):**
```bash
# Run curator to find contradictions + stale facts
mengram_run_agents(agent='curator')

# Run connector to rebuild relationship graph
mengram_run_agents(agent='connector')

# Check Shared-Context vault status
cd /Volumes/BA/DEV/Shared-Context && git log --oneline -20 | head -5
```

**Quarterly (recommended):**
```bash
# Full memory audit
mengram_vault_stats()

# Check for entity drift (reclassify unknown types)
mengram_list_memories()

# Archive old procedures if needed (manually, no built-in archival)
```

---

## References

- **Shared-Context Vault:** `https://github.com/basemaly/shared-context` (git-backed, auto-syncing)
- **Project Location:** `/Volumes/BA/DEV/MaestroAIAgents/Mistral/`
- **Mengram Docs:** Integrated MCP in Claude Code + Cursor + Windsurf + Gemini
- **Workspace Path:** `/Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroAIAgents/`

---

**Version:** 1.0  
**Status:** All 6 phases complete, production-ready  
**Next Review:** After Phase 7 (if scheduled) or quarterly
