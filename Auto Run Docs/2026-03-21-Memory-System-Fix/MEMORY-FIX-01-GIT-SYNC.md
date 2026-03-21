# Phase 1: Install Git Sync Automation

## Objective
Install shell helper functions (`mv-sync`, `mv-pull`, `mv-push`, `mv-status`) and configure launchd job for 15-min auto-sync of Shared-Context vault.

---

- [x] **Create shell helper functions in `~/.zshrc`**

Add these functions to `~/.zshrc` (at the end, before any `eval` statements):

```bash
# Shared-Context git sync helpers
export SHARED_CONTEXT_DIR="/Volumes/BA/DEV/Shared-Context"

mv-status() {
  cd "$SHARED_CONTEXT_DIR"
  git status --short
  echo "---"
  git log -1 --oneline
}

mv-pull() {
  cd "$SHARED_CONTEXT_DIR"
  git pull --rebase origin HEAD 2>&1 | tail -5
}

mv-push() {
  cd "$SHARED_CONTEXT_DIR"
  if git status --short | grep -q .; then
    git add -A
    git commit -m "$(date '+Auto-sync: %Y-%m-%d %H:%M:%S')"
  fi
  git push origin HEAD 2>&1 | tail -3
}

mv-sync() {
  echo "[$(date '+%H:%M:%S')] Syncing Shared-Context..."
  mv-pull
  mv-push
  echo "[$(date '+%H:%M:%S')] Sync complete"
}
```

**Verify after editing:**
```bash
source ~/.zshrc
type mv-status  # Should output: mv-status is a shell function
mv-status       # Should show git status + latest commit
```

---

- [x] **Create launchd plist for 15-min auto-sync**

Create file: `~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>com.basemaly.shared-context-sync</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/zsh</string>
		<string>-c</string>
		<string>source ~/.zshrc &amp;&amp; mv-sync</string>
	</array>
	<key>StartInterval</key>
	<integer>900</integer>
	<key>StandardOutPath</key>
	<string>/tmp/shared-context-sync.log</string>
	<key>StandardErrorPath</key>
	<string>/tmp/shared-context-sync-error.log</string>
	<key>RunAtLoad</key>
	<true/>
</dict>
</plist>
```

**Verify file exists:**
```bash
ls -la ~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist
```

---

- [x] **Load launchd job and verify it runs**

```bash
launchctl load ~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist
```

**Verify job is loaded:**
```bash
launchctl list | grep shared-context-sync
```

Should output a line with the plist label and a PID or "-".

---

- [x] **Test sync functions manually**

```bash
mv-status       # Show current sync status
mv-pull         # Pull latest changes
mv-push         # Stage, commit, and push any local changes
mv-sync         # Full sync (pull + push)
```

All commands should complete without errors and show git output.

---

- [x] **Commit the pending change in MaestroFlow**

```bash
cd /Volumes/BA/DEV/Shared-Context
git status  # Should show: M WORKSPACES/MaestroFlow/WORKSPACE.md
git add WORKSPACES/MaestroFlow/WORKSPACE.md
git commit -m "docs(MaestroFlow): pending workspace changes"
git push origin HEAD
```

**Verify:**
```bash
git status  # Should show: On branch HEAD, nothing to commit
```

---

- [x] **Verify logs after first auto-sync run**

Check that launchd ran successfully:
```bash
cat /tmp/shared-context-sync.log
cat /tmp/shared-context-sync-error.log
```

Should show timestamp entries and no errors.

---

## Success Criteria
- [ ] `mv-status`, `mv-pull`, `mv-push`, `mv-sync` all callable from terminal
- [ ] launchctl shows `com.basemaly.shared-context-sync` as loaded
- [ ] MaestroFlow pending change is committed and pushed
- [ ] Log files exist and show successful sync runs
- [ ] Next auto-sync will run in ~15 minutes from launchd

## Notes
- Sync runs every 900 seconds (15 minutes) via launchd
- Each sync auto-commits staged changes with timestamp
- If network unavailable, git will fail gracefully (logged to stderr)
- To temporarily disable: `launchctl unload ~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist`
- To re-enable: `launchctl load ~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist`

## Implementation Notes (Claudius - 2026-03-21)

**All tasks completed successfully.**

- **Shell functions:** Added to `~/.zshrc` (mv-status, mv-pull, mv-push, mv-sync) ✓
- **Launchd plist:** Created at `~/Library/LaunchAgents/com.basemaly.shared-context-sync.plist` ✓
- **Plist configuration:** Uses bash script at `/Volumes/BA/DEV/Auto Run Docs/Working/sync-shared-context.sh` for reliable execution ✓
- **Job status:** Loaded and running (verified via `launchctl list`) ✓
- **Git status:** Shared-Context repo is clean; MaestroFlow pending change committed and pushed ✓
- **Logs:** Both stdout and stderr logs are created and functional at `/tmp/shared-context-sync.log` and `/tmp/shared-context-sync-error.log` ✓
- **Auto-sync:** Will run every 15 minutes starting from launchd load time ✓

**Key change from spec:** Instead of sourcing `.zshrc` within launchd (which caused issues with non-login shell context), the implementation uses a dedicated bash script (`sync-shared-context.sh`) that performs the sync operations directly. This is more reliable and avoids shell initialization issues.
