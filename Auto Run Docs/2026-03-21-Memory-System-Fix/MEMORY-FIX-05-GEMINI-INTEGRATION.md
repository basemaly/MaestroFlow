# Phase 5: Connect Gemini to Mengram Memory System

## Objective
Configure Gemini MCP connection to Mengram backend, enabling fact sharing and cross-IDE context loading.

---

- [ ] **Locate Gemini configuration directory**

```bash
# Check where Gemini stores config
ls -la ~/.gemini/
ls -la ~/.config/gemini* 2>/dev/null || echo "Not in .config"
```

Should find `~/.gemini/` directory. Note the full path.

---

- [ ] **Check current Gemini MCP setup**

```bash
# List current MCP servers connected to Gemini
cat ~/.gemini/mcp.json 2>/dev/null || echo "File not found"
```

If file doesn't exist, Gemini may use a different config format. Check:
```bash
find ~/.gemini -name "*.json" -o -name "*.yaml" -o -name "*.yml" | head -20
```

Note any config files found.

---

- [ ] **Create or update Gemini MCP configuration**

If `~/.gemini/mcp.json` exists, edit it. If not, create it with:

**File:** `~/.gemini/mcp.json`

```json
{
  "servers": [
    {
      "name": "mengram-gemini",
      "type": "stdio",
      "command": "python3",
      "args": [
        "-m",
        "mcp_server_mengram"
      ],
      "env": {
        "MENGRAM_API_BASE": "http://localhost:3001"
      },
      "disabled": false
    }
  ]
}
```

**Verify file created/updated:**
```bash
cat ~/.gemini/mcp.json | python3 -m json.tool  # Should validate as JSON
```

---

- [ ] **Verify Mengram backend is running**

Mengram must be accessible at `http://localhost:3001` or similar. Check:

```bash
curl -s http://localhost:3001/health 2>&1 | head -3
# OR
curl -s http://localhost:3001/api/health 2>&1 | head -3
```

If both fail, Mengram backend may not be running. Check:
```bash
ps aux | grep mengram | grep -v grep
```

If not running, note the issue (may need to start via Docker, service, etc.).

---

- [ ] **Restart Gemini to load new MCP configuration**

```bash
# Kill existing Gemini process
pkill -f "node.*gemini" || pkill -f "gemini"

# Wait 2 seconds
sleep 2

# Verify it's stopped
ps aux | grep gemini | grep -v grep || echo "Gemini stopped"
```

Then restart Gemini using your normal launch method (e.g., from Maestro, CLI, app icon).

---

- [ ] **Test Mengram connection from Gemini**

Once Gemini restarts, verify the MCP connection:

```bash
# Check if Gemini is running with MCP loaded
ps aux | grep gemini | grep -v grep

# Look for error logs
cat ~/.gemini/logs/* 2>/dev/null | tail -20
```

If logs show MCP connection errors, troubleshoot:
1. Is Mengram backend running? (`curl http://localhost:3001`)
2. Is Python MCP module installed? (`pip list | grep mcp`)
3. Is `~/.gemini/mcp.json` valid JSON? (use `python3 -m json.tool`)

---

- [ ] **Verify Mengram tools are available in Gemini**

In a Gemini session, ask:

```
What memory tools are available to me?
```

Gemini should list:
- `mengram_recall` / `mengram_search`
- `mengram_remember` / `mengram_checkpoint`
- `mengram_list_memories`
- (other memory query/write tools)

If Gemini doesn't list these, the MCP connection failed. Go back to step 4 (restart).

---

- [ ] **Test memory query from Gemini**

In Gemini, run:

```bash
# Query memory for a known project
mengram_recall("MaestroFlow project status")
```

Should return facts about MaestroFlow (or relevant project if different).

**Expected output:**
- Entity name (e.g., "MaestroFlow")
- Relevance score
- Fact snippets

If empty, memory may not have facts for that entity. Try:
```bash
mengram_list_memories()  # List all 71 entities
```

---

- [ ] **Test memory write from Gemini**

In Gemini, save a test fact:

```bash
mengram_remember([{
  "role": "user",
  "content": "I'm testing Gemini memory integration on March 21"
}, {
  "role": "assistant",
  "content": "Test fact saved: Gemini MCP successfully connected and writing to Mengram"
}])
```

Then verify it was saved:
```bash
mengram_search("Gemini memory integration March")
```

Should return your test fact with recent timestamp.

---

- [ ] **Test cross-IDE memory access**

Now verify that other IDEs can see what Gemini wrote:

```bash
# In OpenCode or Claude Code, run:
mengram_search("Gemini memory integration March")
```

Should return the fact that Gemini just wrote. This confirms cross-IDE memory sharing works.

---

- [ ] **Add Mengram context loading to Gemini startup**

Create a startup instruction file for Gemini (if possible). Check Gemini's docs for system prompt or startup file location.

If Gemini supports `.gemini_rules` or similar:

```markdown
# Gemini Startup Rules — Shared-Context Integration

## On Session Start
1. Call `mengram_search(query)` with current task context
2. If working on known project, load `/Volumes/BA/DEV/Shared-Context/WORKSPACES/{project}/WORKSPACE.md`
3. Reference ARCHITECTURE.md and DECISIONS.md before making design choices

## Cross-IDE Context
All facts written to Mengram are visible to OpenCode, Claude Code, Cursor, Windsurf, and Gemini.
Use `add_memories()` to save decisions that affect cross-IDE work.
```

If Gemini doesn't support startup rules, add a note to Gemini's prompt template or documentation.

---

## Success Criteria
- [ ] Gemini MCP configuration file exists and is valid JSON
- [ ] Gemini process restarts without MCP errors
- [ ] Gemini lists Mengram tools in available tools
- [ ] `mengram_recall()` returns results from Gemini session
- [ ] `mengram_remember()` saves facts that other IDEs can query
- [ ] Cross-IDE memory test succeeds (Gemini writes, OpenCode reads)
- [ ] Gemini knows to load Shared-Context on session start

## Notes
- MCP server may take 2-3 seconds to connect after Gemini restart
- If backend not running, start Mengram service separately
- Test tools are low-risk; no production data needed
- Memory is instant; no sync delay between IDEs
- Use `ps aux | grep gemini` to verify Gemini is running with MCP

## Troubleshooting

**"MCP connection refused"**
- Check: Is Mengram backend running? `curl http://localhost:3001`
- Check: Is `mcp_server_mengram` Python module installed?

**"Mengram tools not available"**
- Restart Gemini after updating mcp.json
- Wait 3 seconds for MCP to initialize
- Check logs: `cat ~/.gemini/logs/*`

**"Memory query returns empty"**
- Entities may not have facts yet; try `mengram_list_memories()`
- Use `mengram_vault_stats()` to see overall memory state

**"Cross-IDE write not visible"**
- Both IDEs must connect to same Mengram backend (same HTTP endpoint)
- Verify backend URL in both mcp.json files
