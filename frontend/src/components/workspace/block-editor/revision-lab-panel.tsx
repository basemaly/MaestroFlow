"use client";

import { FilePenLineIcon, Loader2Icon, PlayIcon, XIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { startDocEditRun } from "@/core/doc-editing/api";
import type { DocEditRun, DocEditVersion } from "@/core/doc-editing/types";

const DiffViewer = dynamic(
  () => import("@/components/workspace/diff-viewer").then((m) => m.DiffViewer),
  { ssr: false },
);

type WorkflowMode =
  | "standard"
  | "consensus"
  | "debate-judge"
  | "critic-loop"
  | "strict-bold";
type ModelStrength = "fast" | "strong";

const SKILLS = [
  { id: "writing_refiner", label: "Writing Refiner" },
  { id: "argument_critic", label: "Argument Critic" },
  { id: "humanizer", label: "Humanizer" },
] as const;

const WORKFLOW_MODES: { value: WorkflowMode; label: string }[] = [
  { value: "standard", label: "Standard" },
  { value: "consensus", label: "Consensus" },
  { value: "debate-judge", label: "Debate Judge" },
  { value: "critic-loop", label: "Critic Loop" },
  { value: "strict-bold", label: "Strict Bold" },
];

export interface RevisionLabPanelProps {
  originalContent: string;
  isSelection: boolean;
  onAccept: (markdown: string) => void;
  onClose: () => void;
}

export function RevisionLabPanel({
  originalContent,
  isSelection,
  onAccept,
  onClose,
}: RevisionLabPanelProps) {
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(
    new Set(["writing_refiner"]),
  );
  const [mode, setMode] = useState<WorkflowMode>("standard");
  const [modelStrength, setModelStrength] = useState<ModelStrength>("strong");
  const [isRunning, setIsRunning] = useState(false);
  const [run, setRun] = useState<DocEditRun | null>(null);
  const [activeVersionTab, setActiveVersionTab] = useState<string>("0");

  function toggleSkill(skillId: string) {
    setSelectedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skillId)) {
        if (next.size === 1) return prev; // must keep at least one
        next.delete(skillId);
      } else {
        next.add(skillId);
      }
      return next;
    });
  }

  async function handleRun() {
    setIsRunning(true);
    setRun(null);
    try {
      const result = await startDocEditRun({
        document: originalContent,
        skills: Array.from(selectedSkills),
        workflow_mode: mode,
        model_location: "remote",
        model_strength: modelStrength,
        token_budget: 4000,
      });
      setRun(result);
      // Default to highest-scored version
      if (result.versions.length > 0) {
        const bestIdx = result.versions.reduce((best, v, i) => {
          const bestScore = result.versions[best]?.score ?? 0;
          return v.score > bestScore ? i : best;
        }, 0);
        setActiveVersionTab(String(bestIdx));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Run failed");
    } finally {
      setIsRunning(false);
    }
  }

  const selectedVersion: DocEditVersion | null =
    run && run.versions.length > 0
      ? (run.versions[Number(activeVersionTab)] ?? run.versions[0] ?? null)
      : null;
  const versions = run?.versions ?? [];

  function handleAccept() {
    if (!selectedVersion?.output) return;
    onAccept(selectedVersion.output);
    onClose();
  }

  return (
    <div className="flex h-full flex-col border-l border-border/70 bg-background">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border/70 px-4">
        <div className="flex items-center gap-2">
          <FilePenLineIcon className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold">Revision Lab</span>
          {isSelection && (
            <Badge variant="secondary" className="text-xs">
              Selection
            </Badge>
          )}
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="size-7"
          onClick={onClose}
        >
          <XIcon className="size-4" />
        </Button>
      </div>

      {/* Config strip */}
      <div className="shrink-0 space-y-3 border-b border-border/70 px-4 py-3">
        {/* Skills toggles */}
        <div className="flex flex-wrap gap-1.5">
          {SKILLS.map((skill) => (
            <Button
              key={skill.id}
              type="button"
              size="sm"
              variant={selectedSkills.has(skill.id) ? "default" : "outline"}
              className="h-7 px-2.5 text-xs"
              onClick={() => toggleSkill(skill.id)}
            >
              {skill.label}
            </Button>
          ))}
        </div>

        {/* Mode + strength + run */}
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={mode}
            onValueChange={(v) => setMode(v as WorkflowMode)}
          >
            <SelectTrigger className="h-7 w-36 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WORKFLOW_MODES.map((m) => (
                <SelectItem key={m.value} value={m.value} className="text-xs">
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={modelStrength}
            onValueChange={(v) => setModelStrength(v as ModelStrength)}
          >
            <SelectTrigger className="h-7 w-24 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fast" className="text-xs">
                Fast
              </SelectItem>
              <SelectItem value="strong" className="text-xs">
                Strong
              </SelectItem>
            </SelectContent>
          </Select>

          <Button
            size="sm"
            className="h-7 gap-1.5 px-3 text-xs"
            onClick={() => void handleRun()}
            disabled={isRunning}
          >
            {isRunning ? (
              <Loader2Icon className="size-3 animate-spin" />
            ) : (
              <PlayIcon className="size-3" />
            )}
            Generate takes
          </Button>
        </div>
      </div>

      {/* Results area */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {!isRunning && !run && (
          <div className="flex h-full items-center justify-center p-6">
            <div className="max-w-sm rounded-2xl border border-dashed border-border/80 bg-muted/20 px-5 py-6 text-center">
              <div className="text-sm font-medium">Send this passage through Revision Lab</div>
              <div className="mt-2 text-sm text-muted-foreground">
                Pick editorial voices, choose a workflow, then compare alternate takes side by side.
              </div>
            </div>
          </div>
        )}

        {isRunning && (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2Icon className="size-4 animate-spin" />
            Generating alternate takes...
          </div>
        )}

        {!isRunning && run?.versions.length === 0 && (
          <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
            No versions were returned.
          </div>
        )}

        {!isRunning && (run?.versions.length ?? 0) > 0 && (
          <Tabs
            value={activeVersionTab}
            onValueChange={setActiveVersionTab}
            className="flex h-full flex-col"
          >
            <div className="shrink-0 overflow-x-auto border-b border-border/70">
              <TabsList className="h-9 rounded-none border-0 bg-transparent p-0">
                {versions.map((v, i) => (
                  <TabsTrigger
                    key={v.version_id ?? i}
                    value={String(i)}
                    className="h-9 rounded-none border-b-2 border-transparent px-3 text-xs data-[state=active]:border-primary data-[state=active]:bg-transparent"
                  >
                    {v.skill_name}
                    {v.score > 0 && (
                      <Badge
                        variant="secondary"
                        className="ml-1.5 h-4 px-1 text-[10px]"
                      >
                        {(v.score * 100).toFixed(0)}
                      </Badge>
                    )}
                  </TabsTrigger>
                ))}
                <TabsTrigger
                  value="diff"
                  className="h-9 rounded-none border-b-2 border-transparent px-3 text-xs data-[state=active]:border-primary data-[state=active]:bg-transparent"
                >
                  Diff
                </TabsTrigger>
              </TabsList>
            </div>

            {versions.map((v, i) => (
              <TabsContent
                key={v.version_id ?? i}
                value={String(i)}
                className="mt-0 flex-1 overflow-hidden"
              >
                <ScrollArea className="h-full">
                  <div className="space-y-3 p-4">
                    {/* Version header */}
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {v.skill_name}
                      </span>
                      {v.model_name && (
                        <span className="ml-1">· {v.model_name}</span>
                      )}
                    </div>
                    {/* Score bar */}
                    {v.score > 0 && (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>Score</span>
                          <span>{(v.score * 100).toFixed(0)}</span>
                        </div>
                        <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${Math.min(v.score * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    )}
                    {/* Content */}
                    <pre className="whitespace-pre-wrap text-sm leading-relaxed">
                      {v.output ?? ""}
                    </pre>
                  </div>
                </ScrollArea>
              </TabsContent>
            ))}

            <TabsContent
              value="diff"
              className="mt-0 flex-1 overflow-hidden p-4"
            >
              {selectedVersion?.output ? (
                <DiffViewer
                  original={originalContent}
                  modified={selectedVersion.output}
                  className="h-full"
                />
              ) : (
                <div className="text-sm text-muted-foreground">
                  Select a version tab first.
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>

      {/* Footer */}
      <div className="flex h-16 shrink-0 items-center border-t border-border/70 px-4">
        <Button
          className="w-full"
          disabled={!selectedVersion?.output}
          onClick={handleAccept}
        >
          {isSelection ? "Accept into Composer selection" : "Accept into Composer draft"} →
        </Button>
      </div>
    </div>
  );
}
