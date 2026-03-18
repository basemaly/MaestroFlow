"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainIcon, CalendarIcon, WrenchIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  clearAgentMemory,
  createAgentSchedule,
  deleteAgentSchedule,
  getAgentMemory,
  getAgentTools,
  listAgentSchedules,
  updateAgentMemory,
  updateAgentSchedule,
  updateAgentTools,
  type AgentSchedule,
} from "@/core/agents/api";

type Tab = "memory" | "tools" | "schedules";

export function AgentEditorDialog({
  agentName,
  open,
  onOpenChange,
}: {
  agentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [tab, setTab] = useState<Tab>("memory");

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-xl">
        <SheetHeader className="flex flex-row items-center justify-between border-b px-4 py-3">
          <SheetTitle className="text-base">{agentName}</SheetTitle>
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-sm text-muted-foreground opacity-70 transition-opacity hover:opacity-100"
          >
            <XIcon className="size-4" />
          </button>
        </SheetHeader>

        {/* Tab strip */}
        <div className="flex gap-1 border-b px-4 py-2">
          {(["memory", "tools", "schedules"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                tab === t
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:bg-muted/50"
              }`}
            >
              {t === "memory" && <BrainIcon className="size-3" />}
              {t === "tools" && <WrenchIcon className="size-3" />}
              {t === "schedules" && <CalendarIcon className="size-3" />}
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {tab === "memory" && <MemoryTab agentName={agentName} />}
          {tab === "tools" && <ToolsTab agentName={agentName} />}
          {tab === "schedules" && <SchedulesTab agentName={agentName} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ---- Memory Tab ----

function MemoryTab({ agentName }: { agentName: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["agent-memory", agentName],
    queryFn: () => getAgentMemory(agentName),
  });
  const [draft, setDraft] = useState<string | null>(null);
  const content = draft ?? data?.content ?? "";

  const save = useMutation({
    mutationFn: (c: string) => updateAgentMemory(agentName, c),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-memory", agentName] });
      setDraft(null);
      toast.success("Memory saved");
    },
    onError: () => toast.error("Failed to save memory"),
  });

  const clear = useMutation({
    mutationFn: () => clearAgentMemory(agentName),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-memory", agentName] });
      setDraft("");
      toast.success("Memory cleared");
    },
    onError: () => toast.error("Failed to clear memory"),
  });

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        This text is injected into the agent&apos;s system prompt each session. Use it to give the agent persistent context, preferences, or domain knowledge.
      </p>
      {isLoading ? (
        <div className="text-xs text-muted-foreground">Loading…</div>
      ) : (
        <textarea
          className="min-h-[280px] w-full resize-none rounded-lg border border-border/50 bg-muted/30 px-3 py-2 font-mono text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="No memory yet. Type here to give this agent persistent context…"
          value={content}
          onChange={(e) => setDraft(e.target.value)}
        />
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => save.mutate(content)}
          disabled={save.isPending || draft === null}
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => clear.mutate()}
          disabled={clear.isPending || !content.trim()}
          className="text-destructive hover:text-destructive"
        >
          Clear
        </Button>
      </div>
    </div>
  );
}

// ---- Tools Tab ----

function ToolsTab({ agentName }: { agentName: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["agent-tools", agentName],
    queryFn: () => getAgentTools(agentName),
  });
  const [newTool, setNewTool] = useState("");

  const save = useMutation({
    mutationFn: (tools: string[]) => updateAgentTools(agentName, tools),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-tools", agentName] });
      toast.success("Tools updated");
    },
    onError: () => toast.error("Failed to update tools"),
  });

  const tools = data?.allowed_tools ?? [];

  function addTool() {
    const t = newTool.trim();
    if (!t || tools.includes(t)) return;
    save.mutate([...tools, t]);
    setNewTool("");
  }

  function removeTool(t: string) {
    save.mutate(tools.filter((x) => x !== t));
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        Restrict which tools this agent can use. Empty list = all tools allowed.
      </p>
      {isLoading ? (
        <div className="text-xs text-muted-foreground">Loading…</div>
      ) : (
        <>
          {tools.length === 0 ? (
            <p className="text-xs text-muted-foreground italic">All tools allowed (no restrictions).</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tools.map((t) => (
                <span
                  key={t}
                  className="flex items-center gap-1 rounded-full border border-border/50 bg-muted/40 px-2 py-1 text-xs"
                >
                  {t}
                  <button
                    onClick={() => removeTool(t)}
                    className="ml-0.5 text-muted-foreground hover:text-destructive"
                  >
                    <XIcon className="size-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Tool name (e.g. web_search)"
              value={newTool}
              onChange={(e) => setNewTool(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTool()}
            />
            <Button size="sm" onClick={addTool} disabled={!newTool.trim()}>
              Add
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

// ---- Schedules Tab ----

function SchedulesTab({ agentName }: { agentName: string }) {
  const qc = useQueryClient();
  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ["agent-schedules", agentName],
    queryFn: () => listAgentSchedules(agentName),
    refetchInterval: 30_000,
  });
  const [cronExpr, setCronExpr] = useState("0 9 * * *");
  const [prompt, setPrompt] = useState("");

  const create = useMutation({
    mutationFn: (d: { cron_expr: string; prompt: string }) =>
      createAgentSchedule(agentName, d),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-schedules", agentName] });
      setPrompt("");
      toast.success("Schedule created");
    },
    onError: () => toast.error("Failed to create schedule"),
  });

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateAgentSchedule(agentName, id, { enabled }),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["agent-schedules", agentName] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteAgentSchedule(agentName, id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-schedules", agentName] });
      toast.success("Schedule deleted");
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Schedule this agent to run automatically on a cron schedule.
      </p>
      {isLoading ? (
        <div className="text-xs text-muted-foreground">Loading…</div>
      ) : schedules.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">No schedules yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {schedules.map((s) => (
            <ScheduleRow
              key={s.schedule_id}
              schedule={s}
              onToggle={(enabled) => toggle.mutate({ id: s.schedule_id, enabled })}
              onDelete={() => remove.mutate(s.schedule_id)}
            />
          ))}
        </div>
      )}

      {/* Add form */}
      <div className="rounded-xl border border-border/50 bg-muted/20 p-3 flex flex-col gap-2">
        <p className="text-xs font-medium">New Schedule</p>
        <div className="flex gap-2">
          <input
            className="w-36 rounded-lg border border-border/50 bg-muted/30 px-2 py-1.5 font-mono text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="0 9 * * *"
            value={cronExpr}
            onChange={(e) => setCronExpr(e.target.value)}
          />
          <span className="self-center text-xs text-muted-foreground">cron</span>
        </div>
        <textarea
          className="min-h-[64px] resize-none rounded-lg border border-border/50 bg-muted/30 px-2 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="What should the agent do when triggered?"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <Button
          size="sm"
          className="self-start"
          disabled={!cronExpr.trim() || !prompt.trim() || create.isPending}
          onClick={() => create.mutate({ cron_expr: cronExpr, prompt })}
        >
          Create Schedule
        </Button>
      </div>
    </div>
  );
}

function ScheduleRow({
  schedule,
  onToggle,
  onDelete,
}: {
  schedule: AgentSchedule;
  onToggle: (enabled: boolean) => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/20 p-3">
      <div className="flex-1 min-w-0">
        <p className="font-mono text-xs text-muted-foreground">{schedule.cron_expr}</p>
        <p className="mt-0.5 line-clamp-2 text-xs">{schedule.prompt}</p>
        {schedule.next_run && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            Next: {new Date(schedule.next_run).toLocaleString()}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {/* Toggle */}
        <button
          onClick={() => onToggle(!schedule.enabled)}
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors ${
            schedule.enabled
              ? "bg-emerald-500/20 text-emerald-400"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {schedule.enabled ? "ON" : "OFF"}
        </button>
        <button onClick={onDelete} className="text-muted-foreground hover:text-destructive">
          <XIcon className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
