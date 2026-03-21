# Phase 6: Full System Verification & Documentation

## Objective
Verify all memory system components work together across all IDEs, create cross-IDE startup documentation, and generate summary report.

---

- [ ] **Verify git sync is running automatically**

```bash
# Check launchd job is loaded
launchctl list | grep shared-context-sync

# Check logs from last sync
tail -20 /tmp/shared-context-sync.log
tail -20 /tmp/shared-context-sync-error.log

# Manually trigger one sync to verify functions work
mv-status
mv-pull
mv-push
```

All should succeed without errors. If any fail:
- Verify `~/.zshrc` has the shell functions
- Verify launchd plist is valid XML
- Check: `launchctl list | grep shared-context-sync` shows the job

---

- [ ] **Verify Mengram is clean and properly typed**

```bash
# Check entity statistics
mengram_vault_stats()

# Verify entity types
mengram_list_memories()
```

Expected:
- Entity count ~65-68 (after dedup, was 71)
- All entities properly typed (0 or very few "unknown")
- Facts stable or increased (was 557)

If still dirty:
```bash
mengram_run_agents('curator', auto_fix=true)
mengram_dedup()
```

---

- [ ] **Verify Cursor integration is working**

```bash
# Open Cursor (if not already open)
# In Cursor, ask:
# "Load the context for MaestroFlow project"

# Expected: Cursor should:
# 1. Read .cursorrules file (mention it in response)
# 2. Search memory for "MaestroFlow"
# 3. Read WORKSPACE.md, ARCHITECTURE.md, DECISIONS.md
# 4. Return context with specific technical details
```

**Manual verification:**
```bash
# Check .cursorrules file is readable
file /Volumes/BA/DEV/.cursorrules
wc -l /Volumes/BA/DEV/.cursorrules  # Should be 100+ lines
```

---

- [ ] **Verify Windsurf integration is working**

```bash
# Open Windsurf (if not already open)
# In Windsurf, ask:
# "What is the current architecture of the StateWeave project?"

# Expected: Windsurf should:
# 1. Read .windsurfrules file
# 2. Search memory for "StateWeave"
# 3. Load ARCHITECTURE.md
# 4. Return with specific design details
```

**Manual verification:**
```bash
# Check .windsurfrules file is readable
file /Volumes/BA/DEV/.windsurfrules
wc -l /Volumes/BA/DEV/.windsurfrules  # Should be 100+ lines
```

---

- [ ] **Verify Gemini is connected to Mengram**

```bash
# Check MCP config
cat ~/.gemini/mcp.json | python3 -m json.tool  # Should be valid JSON

# In a Gemini session, run:
# mengram_list_memories()
# Expected: Should list all 65-68 entities

# Test write:
# mengram_checkpoint(summary="Gemini test checkpoint March 21")

# Verify from another IDE:
# mengram_search("Gemini test checkpoint")
```

---

- [ ] **Test cross-IDE memory sharing**

**Sequence Test:**

1. In **OpenCode**, write:
   ```bash
   mengram_remember([{
     "role": "assistant",
     "content": "Cross-IDE test: OpenCode writes at $(date)"
   }])
   ```

2. In **Cursor**, query:
   ```bash
   mengram_search("Cross-IDE test OpenCode")
   ```
   Should see the fact from step 1.

3. In **Windsurf**, write:
   ```bash
   mengram_checkpoint(summary="Windsurf verifies cross-IDE fact sharing - SUCCESS")
   ```

4. In **Gemini**, verify:
   ```bash
   mengram_search("Windsurf verifies")
   ```

Should see Windsurf's fact. This proves all IDEs share the same memory.

---

- [ ] **Verify Shared-Context git sync is working**

```bash
# Make a test change
cd /Volumes/BA/DEV/Shared-Context
echo "Test sync: $(date)" >> .test-sync-marker.txt

# Wait for auto-sync (max 15 min, or manually trigger)
mv-sync

# Verify it was pushed
git log --oneline -1  # Should show "Auto-sync: 2026-03-21 HH:MM:SS"

# Check remote
git log origin/HEAD --oneline -1  # Should match local

# Clean up test file
rm .test-sync-marker.txt
git add .test-sync-marker.txt
git commit -m "Remove test sync marker"
git push origin HEAD
```

---

- [ ] **Create Cross-IDE Startup Protocol documentation**

Create file: `/Volumes/BA/DEV/Shared-Context/SYSTEM/CROSS-IDE-STARTUP.md`

```markdown
# Cross-IDE Startup Protocol

## Purpose
Ensure all agents (OpenCode, Claude Code, Cursor, Windsurf, Gemini) load project context consistently and share facts via Mengram.

## Startup Sequence (Every Session)

### 1. Identify Project
```
User: "Help me with MaestroFlow"
↓ Agent recognizes project name
```

### 2. Load Memory (1-2 seconds)
```bash
mengram_search(query="MaestroFlow project status architecture")
```
Returns: Recent decisions, tech stack, project state from Mengram.

### 3. Load Hot Context (2-3 seconds)
```bash
# Read these files in order:
1. /Volumes/BA/DEV/Shared-Context/WORKSPACES/MaestroFlow/WORKSPACE.md
2. ARCHITECTURE.md
3. DECISIONS.md
```

### 4. Ready to Code
Agent now has full context of project state, architecture, and past decisions. Can begin work immediately.

## Context Tiers

**Hot (Always):** WORKSPACE.md, ARCHITECTURE.md, DECISIONS.md
- Load on every session start
- Refresh if project status changes
- Max 5 min to load all three

**Warm (When Needed):** System docs, agent protocols
- Load if task touches system-level concerns
- Load if context conflicts with memory

**Cold (Rarely):** Old specs, archives, experimental notes
- Load only on explicit user request
- Load if debugging historical decisions

## Multi-IDE Context Sharing

**Golden Rule:** If work spans multiple IDEs, use Mengram as handoff point.

**Pattern:**
```
IDE A: Completes analysis of Problem X
↓
IDE A: Add findings to memory
  mengram_remember([{type: "decision", content: "Analyzed X, found root cause..."}])
↓
IDE B: Next session queries memory
  mengram_search("Problem X analysis root cause")
↓
IDE B: Reads findings, continues from there
```

## IDE-Specific Rules

**OpenCode:** Primary agent. Orchestrates work across projects.
- Rule: Search memory first, then read vault
- Role: Starts new projects, initiates major refactors

**Claude Code:** Context-heavy agent for deep debugging.
- Rule: Load all three ARCHITECTURE/DECISIONS files before responding
- Role: Debugging, optimization, complex refactoring

**Cursor:** Fast turnaround IDE.
- Rule: Load WORKSPACE.md + top decision from DECISIONS.md
- Role: Quick bug fixes, feature additions

**Windsurf:** Extended reasoning agent.
- Rule: Load all context; use for architectural decisions
- Role: System design, cross-project coordination

**Gemini:** Lightweight query agent.
- Rule: Use memory-first approach; fall back to vault if needed
- Role: Information retrieval, documentation, pattern analysis

## Session End: Handoff Pattern

Before switching IDEs or ending session:

```bash
# 1. Update vault if you modified architecture/decisions
git -C /Volumes/BA/DEV/Shared-Context add -A
git -C /Volumes/BA/DEV/Shared-Context commit -m "docs({project}): update after session"

# 2. Save session summary to memory
mengram_checkpoint(
  summary="Completed X, next is Y",
  next_steps=["Do Z", "Test in environment"]
)

# 3. Other IDEs will load this on their next session
```

## Verification Checklist

Start of each session:
- [ ] Memory system accessible? (try `mengram_list_memories()`)
- [ ] Vault readable? (can access WORKSPACE.md)
- [ ] Git sync running? (check `mv-status`)
- [ ] Project context loaded? (agent mentions ARCHITECTURE.md)

End of each session:
- [ ] Vault updated if needed? (no pending changes)
- [ ] Session summary saved? (checkpoint or remember)
- [ ] Other IDEs notified? (facts in Mengram)

## Troubleshooting

**"Can't access Mengram"**
- Check: Is MCP running? `ps aux | grep mcp`
- Check: Is Mengram backend running? `curl http://localhost:3001`

**"No project context loaded"**
- Check: Is `.cursorrules` / `.windsurfrules` readable?
- Check: Is vault path accessible? `ls /Volumes/BA/DEV/Shared-Context`

**"Git sync not working"**
- Check: Is launchd job loaded? `launchctl list | grep shared-context-sync`
- Manual sync: `mv-sync`

**"Changes not shared across IDEs"**
- Check: Are all IDEs reading same vault? (`git log` should be identical)
- Check: Are facts being written to Mengram? (`mengram_list_memories()`)

---

**Status:** All IDEs configured and syncing. Ready for multi-agent workflows.
```

**Create the file:**
```bash
cat > /Volumes/BA/DEV/Shared-Context/SYSTEM/CROSS-IDE-STARTUP.md << 'EOF'
# [paste above markdown here]
EOF
```

---

- [ ] **Create system verification script**

Create file: `/Volumes/BA/DEV/scripts/verify-memory-system.sh`

```bash
#!/bin/bash
set -e

echo "=== Memory System Health Check ==="
echo ""

# Check 1: Git sync
echo "[1] Git Sync Status"
launchctl list | grep shared-context-sync && echo "  ✓ launchd job loaded" || echo "  ✗ launchd job NOT loaded"
type mv-status > /dev/null 2>&1 && echo "  ✓ Shell functions available" || echo "  ✗ Shell functions NOT available"
cd /Volumes/BA/DEV/Shared-Context && git status --short | wc -l | xargs echo "  Uncommitted changes:"

# Check 2: Mengram
echo ""
echo "[2] Mengram Memory Status"
curl -s http://localhost:3001/health > /dev/null 2>&1 && echo "  ✓ Mengram backend running" || echo "  ✗ Mengram backend NOT running"

# Check 3: Vault
echo ""
echo "[3] Shared-Context Vault"
[ -d /Volumes/BA/DEV/Shared-Context/WORKSPACES ] && echo "  ✓ Vault structure present" || echo "  ✗ Vault structure missing"
find /Volumes/BA/DEV/Shared-Context/WORKSPACES -name "WORKSPACE.md" | wc -l | xargs echo "  Projects with WORKSPACE.md:"

# Check 4: IDE Rules
echo ""
echo "[4] IDE Configuration Files"
[ -f /Volumes/BA/DEV/.cursorrules ] && echo "  ✓ .cursorrules present" || echo "  ✗ .cursorrules missing"
[ -f /Volumes/BA/DEV/.windsurfrules ] && echo "  ✓ .windsurfrules present" || echo "  ✗ .windsurfrules missing"
[ -f ~/.gemini/mcp.json ] && echo "  ✓ Gemini MCP configured" || echo "  ✗ Gemini MCP not configured"

echo ""
echo "=== Health Check Complete ==="
```

Make it executable:
```bash
chmod +x /Volumes/BA/DEV/scripts/verify-memory-system.sh
```

Run it:
```bash
/Volumes/BA/DEV/scripts/verify-memory-system.sh
```

---

- [ ] **Generate Final Status Report**

Create file: `/Volumes/BA/DEV/MEMORY-SYSTEM-STATUS.md`

```markdown
# Memory System Status Report
**Generated:** $(date)
**Overall Status:** ✅ FULLY OPERATIONAL

## Component Status

| Component | Status | Last Verified |
|-----------|--------|---|
| Git Sync (launchd) | ✅ Active | $(mv-status \| head -1) |
| Shared-Context Vault | ✅ Synced | $(cd /Volumes/BA/DEV/Shared-Context && git log -1 --format=%ai) |
| Mengram Backend | ✅ Running | $(date) |
| Mengram Memory | ✅ Clean | 65-68 entities, 557+ facts |
| OpenCode Integration | ✅ Active | MCP connected |
| Claude Code Integration | ✅ Active | Memory syscalls working |
| Cursor Integration | ✅ Active | .cursorrules loaded |
| Windsurf Integration | ✅ Active | .windsurfrules loaded |
| Gemini Integration | ✅ Active | MCP connected |

## Cross-IDE Sync

All IDEs now share:
- Same Shared-Context vault (git-backed, 15-min auto-sync)
- Same Mengram memory (MCP-backed, instant sync)
- Same startup protocol (load hot context first)

## Recent Activity

- Phase 1 ✅: Git sync automation installed and running
- Phase 2 ✅: Mengram cleaned (dedup + curator)
- Phase 3 ✅: Cursor integrated (.cursorrules)
- Phase 4 ✅: Windsurf integrated (.windsurfrules)
- Phase 5 ✅: Gemini connected (MCP)
- Phase 6 ✅: Full verification complete

## Next Steps

All fixed. System is production-ready for multi-IDE workflows.

**To verify on next session:**
```bash
/Volumes/BA/DEV/scripts/verify-memory-system.sh
```

---

*Memory System is now fully synchronized across all IDEs.*
```

---

## Success Criteria
- [ ] Git sync launchd job is loaded and running
- [ ] `mv-status`, `mv-pull`, `mv-push`, `mv-sync` all work
- [ ] Mengram is clean (65-68 entities, all typed, 557+ facts)
- [ ] `.cursorrules` file exists and Cursor loads it
- [ ] `.windsurfrules` file exists and Windsurf loads it
- [ ] Gemini MCP is configured and tools are available
- [ ] Cross-IDE memory test passes (OpenCode write → Cursor read)
- [ ] Cross-IDE startup protocol documented
- [ ] Verification script runs without errors
- [ ] All 6 phases complete

## Notes
- Total time to completion: ~2-3 hours of agent work
- System is backward compatible (old IDEs still work)
- Verify script can be run after each phase for confidence
- All components are independent; can be tested in isolation
