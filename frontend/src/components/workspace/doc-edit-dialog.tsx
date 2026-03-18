"use client";

import {
  ArrowUpRightIcon,
  CheckCircle2Icon,
  DiffIcon,
  FilePenLineIcon,
  Loader2Icon,
  Maximize2Icon,
  MedalIcon,
  Minimize2Icon,
  PaperclipIcon,
  Settings2Icon,
  SparklesIcon,
  XIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

const DiffViewer = dynamic(
  () => import("./diff-viewer").then((m) => ({ default: m.DiffViewer })),
  { ssr: false, loading: () => <div className="flex h-40 items-center justify-center text-muted-foreground text-sm">Loading diff view...</div> },
);

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  useSelectDocEditVersion,
  useStartDocEditRun,
  useUploadDocEditFile,
} from "@/core/doc-editing/hooks";
import type { DocEditRun } from "@/core/doc-editing/types";
import { useCreateDocument } from "@/core/documents/hooks";
import { useModels } from "@/core/models/hooks";
import { env } from "@/env";
import { cn } from "@/lib/utils";

type ModelLocation = "local" | "remote" | "mixed";
type ModelStrength = "fast" | "cheap" | "strong";
type WorkflowMode =
  | "standard"
  | "consensus"
  | "debate-judge"
  | "critic-loop"
  | "strict-bold";

const SKILL_OPTIONS = [
  { value: "writing-refiner", label: "Writing Refiner" },
  { value: "argument-critic", label: "Argument Critic" },
  { value: "humanizer", label: "Humanizer" },
] as const;
const DEFAULT_SKILLS = ["writing-refiner", "argument-critic"];
const BASE_SKILL_VALUES = new Set(SKILL_OPTIONS.map((skill) => skill.value));
const WORKFLOW_MODE_OPTIONS: Array<{
  value: WorkflowMode;
  label: string;
  description: string;
}> = [
  {
    value: "consensus",
    label: "Consensus",
    description: "Merge the top two versions into one balanced draft.",
  },
  {
    value: "debate-judge",
    label: "Debate + Judge",
    description: "Use a neutral judge pass to synthesize the strongest case from both leading drafts.",
  },
  {
    value: "critic-loop",
    label: "Critic Loop",
    description: "Treat the runner-up as critique and revise the best draft once.",
  },
  {
    value: "strict-bold",
    label: "Strict vs Bold",
    description: "Produce one conservative pass and one sharper high-impact rewrite.",
  },
  {
    value: "standard",
    label: "Standard",
    description: "Skip synthesis and review only the raw skill/model outputs.",
  },
];
const selectedToggleItemClass =
  "rounded-full border-2 border-border/80 px-4 data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-foreground data-[state=on]:shadow-sm";

function formatSkillLabel(skillName: string) {
  if (skillName === "writing-refiner") {
    return "Writing Refiner";
  }
  if (skillName === "argument-critic") {
    return "Argument Critic";
  }
  if (skillName === "humanizer") {
    return "Humanizer";
  }
  if (skillName === "consensus") {
    return "Consensus Merge";
  }
  if (skillName === "debate-judge") {
    return "Debate Judge";
  }
  if (skillName === "critic-loop") {
    return "Critic Loop";
  }
  if (skillName === "strict-fidelity") {
    return "Strict Fidelity";
  }
  if (skillName === "bold-rewrite") {
    return "Bold Rewrite";
  }
  return skillName;
}

function getSelectableSkills(versionSkillNames: string[] | undefined) {
  const filtered = (versionSkillNames ?? []).filter(
    (skillName): skillName is string => BASE_SKILL_VALUES.has(skillName as (typeof SKILL_OPTIONS)[number]["value"]),
  );
  return filtered.length > 0 ? Array.from(new Set(filtered)) : DEFAULT_SKILLS;
}

function resolveModelStrength(
  mode: "flash" | "thinking" | "pro" | "ultra" | undefined,
): ModelStrength {
  if (mode === "pro" || mode === "ultra") {
    return "strong";
  }
  return "fast";
}

function DocEditStudioHeader({ title }: { title: string }) {
  return (
    <div className="mb-6 flex flex-col gap-2 text-left">
      <div className="flex items-center gap-2 text-lg leading-none font-semibold">
        <SparklesIcon className="size-4" />
        {title}
      </div>
      <div className="text-muted-foreground text-sm">
        Paste markdown or upload a supported file, run multiple editorial skills in parallel, then choose the winner.
      </div>
    </div>
  );
}

export function DocEditStudio({
  disabled,
  mode,
  initialRun,
  embedded = false,
  initialDocument = "",
}: {
  disabled?: boolean;
  mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
  initialRun?: DocEditRun | null;
  embedded?: boolean;
  initialDocument?: string;
}) {
  const [document, setDocument] = useState(initialRun?.document ?? initialDocument);
  const [skills, setSkills] = useState<string[]>(
    getSelectableSkills(initialRun?.versions?.map((version) => version.skill_name)),
  );
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>(
    initialRun?.workflow_mode ?? "consensus",
  );
  const [modelLocation, setModelLocation] = useState<ModelLocation>("mixed");
  const [modelStrength, setModelStrength] = useState<ModelStrength>(
    resolveModelStrength(mode),
  );
  const [preferredModel, setPreferredModel] = useState("");
  const [compareModelsEnabled, setCompareModelsEnabled] = useState(false);
  const [modelA, setModelA] = useState("");
  const [modelB, setModelB] = useState("");
  const [projectKey, setProjectKey] = useState(initialRun?.project_key ?? "");
  const [surfSenseSearchSpaceId, setSurfSenseSearchSpaceId] = useState(
    initialRun?.surfsense_search_space_id ? String(initialRun.surfsense_search_space_id) : "",
  );
  const [tokenBudget, setTokenBudget] = useState("4000");
  const [run, setRun] = useState<DocEditRun | null>(initialRun ?? null);
  const [compareVersionId, setCompareVersionId] = useState<string | null>(
    initialRun?.selected_version_id ??
      initialRun?.versions?.[0]?.version_id ??
      null,
  );
  const [viewMode, setViewMode] = useState<"side-by-side" | "diff">("side-by-side");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { models } = useModels();
  const router = useRouter();
  const createDocument = useCreateDocument();

  const startRun = useStartDocEditRun();
  const selectVersion = useSelectDocEditVersion();
  const uploadFile = useUploadDocEditFile();

  useEffect(() => {
    if (!initialRun) {
      return;
    }
    setRun(initialRun);
    setDocument(initialRun.document ?? "");
    setWorkflowMode(initialRun.workflow_mode ?? "consensus");
    setProjectKey(initialRun.project_key ?? "");
    setSurfSenseSearchSpaceId(
      initialRun.surfsense_search_space_id ? String(initialRun.surfsense_search_space_id) : "",
    );
    if (initialRun.versions.length > 0) {
      setCompareVersionId(
        initialRun.selected_version_id ?? initialRun.versions[0]?.version_id ?? null,
      );
      setSkills(getSelectableSkills(initialRun.versions.map((version) => version.skill_name)));
    }
  }, [initialRun]);

  useEffect(() => {
    if (run || startRun.isPending || selectVersion.isPending) {
      return;
    }
    setModelStrength(resolveModelStrength(mode));
  }, [mode, run, selectVersion.isPending, startRun.isPending]);

  const deferredDocument = useDeferredValue(document);
  const wordCount = useMemo(
    () => deferredDocument.trim().split(/\s+/).filter(Boolean).length,
    [deferredDocument],
  );
  const runTitle = run?.title ?? "Parallel Document Editing";
  const invalidBudget =
    tokenBudget.trim().length > 0 &&
    Number.parseInt(tokenBudget, 10) < 250;

  const sortedVersions = useMemo(() => run?.versions ?? [], [run]);
  const deferredVersions = useDeferredValue(sortedVersions);
  const versionsSummaryBySkill = useMemo(
    () =>
      new Map(
        run?.review_payload?.versions_summary?.map((item) => [item.version_id, item]) ?? [],
      ),
    [run?.review_payload?.versions_summary],
  );
  const comparedVersion = useMemo(
    () =>
      deferredVersions.find((version) => version.version_id === compareVersionId) ??
      deferredVersions[0] ??
      null,
    [compareVersionId, deferredVersions],
  );
  const canSubmit =
    document.trim().length > 0 &&
    skills.length > 0 &&
    !(disabled ?? false) &&
    !invalidBudget &&
    (!compareModelsEnabled ||
      (modelA.length > 0 && modelB.length > 0 && modelA !== modelB)) &&
    !uploadFile.isPending &&
    !selectVersion.isPending;
  const selectedModels = [modelA, modelB].map((value) => value.trim()).filter(Boolean);
  const modelPassCount = compareModelsEnabled ? selectedModels.length || 1 : 1;
  const selectedSummary = `${skills.length} skill${skills.length === 1 ? "" : "s"} x ${modelPassCount} model${modelPassCount === 1 ? "" : "s"} · ${WORKFLOW_MODE_OPTIONS.find((option) => option.value === workflowMode)?.label ?? "Consensus"}`;
  const isBusy = startRun.isPending || selectVersion.isPending || uploadFile.isPending;

  useEffect(() => {
    if (deferredVersions.length === 0) {
      if (compareVersionId !== null) {
        setCompareVersionId(null);
      }
      return;
    }
    if (
      !compareVersionId ||
      !deferredVersions.some((version) => version.version_id === compareVersionId)
    ) {
      setCompareVersionId(run?.selected_version_id ?? deferredVersions[0]?.version_id ?? null);
    }
  }, [compareVersionId, deferredVersions, run?.selected_version_id]);

  function resetStudio() {
    setRun(null);
    setDocument("");
    setCompareVersionId(null);
    setTokenBudget("4000");
    setSkills(DEFAULT_SKILLS);
    setWorkflowMode("consensus");
    setModelLocation("mixed");
    setModelStrength(resolveModelStrength(mode));
    setPreferredModel("");
    setCompareModelsEnabled(false);
    setModelA("");
    setModelB("");
    setProjectKey("");
    setSurfSenseSearchSpaceId("");
  }

  async function handleRun() {
    if (!canSubmit) {
      return;
    }
    try {
      const parsedBudget = Number.parseInt(tokenBudget, 10);
      if (!Number.isNaN(parsedBudget) && parsedBudget < 250) {
        toast.error("Token budget must be at least 250");
        return;
      }
      const nextRun = await startRun.mutateAsync({
        document: document.trim(),
        skills,
        workflow_mode: workflowMode,
        model_location: modelLocation,
        model_strength: modelStrength,
        preferred_model: preferredModel.trim() || undefined,
        selected_models: compareModelsEnabled ? selectedModels : undefined,
        project_key: projectKey.trim() || undefined,
        surfsense_search_space_id:
          surfSenseSearchSpaceId.trim().length > 0
            ? Number.parseInt(surfSenseSearchSpaceId, 10)
            : undefined,
        token_budget: Number.isNaN(parsedBudget) ? 4000 : parsedBudget,
      });
      setRun(nextRun);
      setCompareVersionId(
        nextRun.selected_version_id ?? nextRun.versions[0]?.version_id ?? null,
      );
      toast.success(
        nextRun.status === "awaiting_selection"
          ? "Parallel edits are ready for review"
          : "Document edit run completed",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleSelect(versionId: string) {
    if (!run) {
      return;
    }
    try {
      const nextRun = await selectVersion.mutateAsync({
        runId: run.run_id,
        versionId,
      });
      setRun(nextRun);
      setCompareVersionId(versionId);
      const selectedVersion = nextRun.versions.find((version) => version.version_id === versionId);
      toast.success(`Selected ${formatSkillLabel(selectedVersion?.skill_name ?? versionId)} as the final version`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleFilePicked(file: File | null) {
    if (!file) {
      return;
    }
    try {
      const uploaded = await uploadFile.mutateAsync(file);
      setDocument(uploaded.document);
      toast.success(`Loaded ${uploaded.filename}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleOpenVersionInEditor(versionId: string) {
    const version = sortedVersions.find((item) => (item.version_id ?? item.skill_name) === versionId);
    const content =
      version?.output ??
      (version?.version_id ? versionsSummaryBySkill.get(version.version_id)?.preview ?? "" : "");
    if (!content.trim()) {
      toast.error("That version has no editable content yet");
      return;
    }
    try {
      const documentRecord = await createDocument.mutateAsync({
        title: `${runTitle} · ${formatSkillLabel(version?.skill_name ?? versionId)}`,
        content_markdown: content,
        source_run_id: run?.run_id,
        source_version_id: version?.version_id ?? versionId,
      });
      void router.push(`/workspace/docs/${documentRecord.doc_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="grid h-full grid-cols-1 overflow-hidden xl:grid-cols-[0.98fr_1.32fr] 2xl:grid-cols-[1fr_1.3fr]">
      <div className={cn("overflow-y-auto border-border/70 bg-muted/20 p-6", !embedded && "border-r")}>
        <DocEditStudioHeader title={runTitle} />

        <div className="space-y-5">
          <div className="space-y-2 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-medium">Document</div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadFile.isPending}
              >
                {uploadFile.isPending ? (
                  <Loader2Icon className="size-4 animate-spin" />
                ) : (
                  <PaperclipIcon className="size-4" />
                )}
                Upload File
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".md,.markdown,.txt,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
                onChange={(event) =>
                  void handleFilePicked(event.target.files?.[0] ?? null)
                }
              />
            </div>
            <Textarea
              className="min-h-[280px] resize-none bg-background"
              placeholder="Paste markdown here..."
              value={document}
              onChange={(event) => setDocument(event.target.value)}
            />
            <div className="text-muted-foreground text-xs">
              {wordCount} words
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="text-sm font-medium">Skills</div>
            <ToggleGroup
              type="multiple"
              variant="outline"
              className="flex flex-wrap gap-2"
              value={skills}
              onValueChange={(value) => setSkills(value.length > 0 ? value : skills)}
            >
              {SKILL_OPTIONS.map((skill) => (
                <ToggleGroupItem
                  key={skill.value}
                  value={skill.value}
                  className={selectedToggleItemClass}
                >
                  {skill.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div>
              <div className="text-sm font-medium">Workflow Mode</div>
              <div className="text-muted-foreground text-xs">
                Add an optional merge, judge, or divergent pass after the raw skill outputs are generated.
              </div>
            </div>
            <Select
              value={workflowMode}
              onValueChange={(value) => {
                if (
                  value === "standard" ||
                  value === "consensus" ||
                  value === "debate-judge" ||
                  value === "critic-loop" ||
                  value === "strict-bold"
                ) {
                  setWorkflowMode(value);
                }
              }}
            >
              <SelectTrigger className="w-full bg-background">
                <SelectValue placeholder="Choose workflow mode" />
              </SelectTrigger>
              <SelectContent>
                {WORKFLOW_MODE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="rounded-xl border border-border/70 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              {WORKFLOW_MODE_OPTIONS.find((option) => option.value === workflowMode)?.description}
            </div>
          </div>

          <div className="space-y-4 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="flex items-center gap-2">
              <Settings2Icon className="size-4 text-muted-foreground" />
              <div>
                <div className="text-sm font-medium">Model Routing</div>
                <div className="text-muted-foreground text-xs">
                  Choose where the models should run, how aggressive the quality target should be, and optionally hint a specific alias.
                </div>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <div className="text-sm font-medium">Model Location</div>
                <Select
                  value={modelLocation}
                  onValueChange={(value) => {
                    if (value === "local" || value === "remote" || value === "mixed") {
                      setModelLocation(value);
                    }
                  }}
                >
                  <SelectTrigger className="w-full bg-background">
                    <SelectValue placeholder="Choose model location" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mixed">Mixed</SelectItem>
                    <SelectItem value="remote">Remote</SelectItem>
                    <SelectItem value="local">Local</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium">Model Strength</div>
                <Select
                  value={modelStrength}
                  onValueChange={(value) => {
                    if (value === "fast" || value === "cheap" || value === "strong") {
                      setModelStrength(value);
                    }
                  }}
                >
                  <SelectTrigger className="w-full bg-background">
                    <SelectValue placeholder="Choose model strength" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fast">Fast</SelectItem>
                    <SelectItem value="cheap">Cheap</SelectItem>
                    <SelectItem value="strong">Strong</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Preferred Model</div>
              <Input
                className="bg-background"
                value={preferredModel}
                placeholder="Optional: gpt-5.2-mini, gemini flash, qwen 32b..."
                onChange={(event) => setPreferredModel(event.target.value)}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
              />
              <div className="text-muted-foreground text-xs">
                Routed through the closest configured LiteLLM model match when possible.
              </div>
            </div>
          </div>

          <div className="grid gap-4 rounded-2xl border border-border/70 bg-background/60 p-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="text-sm font-medium">SurfSense Project Key</div>
              <Input
                className="bg-background"
                value={projectKey}
                placeholder="Optional: client-alpha"
                onChange={(event) => setProjectKey(event.target.value)}
                autoCapitalize="off"
                autoCorrect="off"
                spellCheck={false}
              />
              <div className="text-muted-foreground text-xs">
                Routes retrieval and export through a stable project-to-search-space mapping when configured.
              </div>
            </div>
            <div className="space-y-2">
              <div className="text-sm font-medium">SurfSense Search Space</div>
              <Input
                className="bg-background"
                value={surfSenseSearchSpaceId}
                placeholder="Optional: 12"
                inputMode="numeric"
                onChange={(event) =>
                  setSurfSenseSearchSpaceId(event.target.value.replace(/[^\d]/g, ""))
                }
              />
              <div className="text-muted-foreground text-xs">
                Use this for one-off exports into a specific SurfSense search space.
              </div>
            </div>
          </div>

          <div className="space-y-3 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium">Two-Model Compare</div>
                <div className="text-muted-foreground text-xs">
                  Run the same edit pass across two specific models at once.
                </div>
              </div>
              <Button
                size="sm"
                variant={compareModelsEnabled ? "default" : "outline"}
                className={cn(
                  "rounded-full border-2 px-4",
                  compareModelsEnabled && "border-primary bg-primary/95 text-primary-foreground shadow-sm",
                )}
                onClick={() => setCompareModelsEnabled((value) => !value)}
                aria-pressed={compareModelsEnabled}
              >
                {compareModelsEnabled ? "Enabled" : "Enable"}
              </Button>
            </div>
            {compareModelsEnabled && (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-sm font-medium">Model A</div>
                  <Select value={modelA} onValueChange={setModelA}>
                    <SelectTrigger className="w-full bg-background">
                      <SelectValue placeholder="Choose first model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem key={model.name} value={model.name}>
                          {model.display_name ?? model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium">Model B</div>
                  <Select value={modelB} onValueChange={setModelB}>
                    <SelectTrigger className="w-full bg-background">
                      <SelectValue placeholder="Choose second model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model) => (
                        <SelectItem key={model.name} value={model.name}>
                          {model.display_name ?? model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
            {compareModelsEnabled && modelA && modelB && modelA === modelB && (
              <div className="text-xs text-destructive">
                Choose two different models for a compare pass.
              </div>
            )}
          </div>

          <div className="space-y-2 rounded-2xl border border-border/70 bg-background/60 p-4">
            <div className="text-sm font-medium">Token Budget</div>
            <Input
              className="bg-background"
              value={tokenBudget}
              inputMode="numeric"
              onChange={(event) =>
                setTokenBudget(event.target.value.replace(/[^\d]/g, ""))
              }
            />
            {invalidBudget && (
              <div className="text-xs text-destructive">
                Minimum token budget is 250.
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              className="min-w-[10rem] rounded-full border-2 border-transparent px-5"
              onClick={handleRun}
              disabled={!canSubmit || startRun.isPending}
            >
              {startRun.isPending ? (
                <Loader2Icon className="size-4 animate-spin" />
              ) : (
                <SparklesIcon className="size-4" />
              )}
              Run Versions
            </Button>
            <Button
              variant="outline"
              className="min-w-[8rem] rounded-full border-2 px-5"
              onClick={resetStudio}
              disabled={isBusy}
            >
              Reset
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-dashed border-border/70 bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
            <Badge variant="outline">{selectedSummary}</Badge>
            {!!preferredModel.trim() && (
              <Badge variant="outline">Hint {preferredModel.trim()}</Badge>
            )}
            {!!projectKey.trim() && (
              <Badge variant="outline">Project {projectKey.trim()}</Badge>
            )}
            {!!surfSenseSearchSpaceId.trim() && (
              <Badge variant="outline">SurfSense {surfSenseSearchSpaceId.trim()}</Badge>
            )}
            {compareModelsEnabled && modelA && modelB ? `: ${modelA} + ${modelB}` : ""}
          </div>
        </div>
      </div>

      <div className="flex flex-col overflow-hidden bg-background p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">Review & Compare</div>
            <div className="text-muted-foreground text-xs">
              {run
                ? run.status === "completed"
                  ? "Final version exported"
                  : run.review_payload?.instruction ??
                    "Select a version to finalize the run."
                : "Run a document edit job to compare outputs here."}
            </div>
            {run && (
              <div className="text-muted-foreground mt-1 text-[11px]">
                {run.run_id}
                {run.workflow_mode
                  ? ` · ${WORKFLOW_MODE_OPTIONS.find((option) => option.value === run.workflow_mode)?.label ?? run.workflow_mode}`
                  : ""}
              </div>
            )}
          </div>
          {run?.status && (
            <Badge variant={run.status === "completed" ? "default" : "secondary"}>
              {run.status === "completed" ? "Completed" : "Awaiting Selection"}
            </Badge>
          )}
        </div>

        {run?.final_path && (
          <Card className="mb-4 gap-3 border-emerald-500/35 bg-emerald-500/5 py-4">
            <CardHeader className="px-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCircle2Icon className="size-4 text-emerald-600" />
                Final Version Saved
              </CardTitle>
              <CardDescription>{run.final_path}</CardDescription>
            </CardHeader>
          </Card>
        )}

        {run && (
          <div className="mb-4">
            <ToggleGroup
              type="single"
              variant="outline"
              className="flex flex-wrap gap-2"
              value={compareVersionId ?? undefined}
              onValueChange={(value) => setCompareVersionId(value || null)}
            >
              {sortedVersions.map((version) => (
                <ToggleGroupItem
                  key={version.version_id ?? version.skill_name}
                  value={version.version_id ?? version.skill_name}
                  className={selectedToggleItemClass}
                >
                  {formatSkillLabel(version.skill_name)}
                  {version.model_name ? ` · ${version.model_name}` : ""}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}

        {(document || comparedVersion) && (
          <div className="mb-6">
            <div className="mb-3 flex items-center gap-2">
              <Button
                variant={viewMode === "side-by-side" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("side-by-side")}
              >
                Side by Side
              </Button>
              <Button
                variant={viewMode === "diff" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("diff")}
              >
                <DiffIcon className="mr-1.5 size-4" />
                Diff
              </Button>
              {comparedVersion && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleOpenVersionInEditor(comparedVersion.version_id ?? comparedVersion.skill_name)}
                  disabled={createDocument.isPending}
                >
                  <ArrowUpRightIcon className="mr-1.5 size-4" />
                  Open in Block Editor
                </Button>
              )}
            </div>

            {viewMode === "diff" ? (
              <DiffViewer
                original={document.length > 0 ? document : (run?.document ?? "")}
                modified={
                  comparedVersion?.output ??
                  (comparedVersion?.version_id
                    ? versionsSummaryBySkill.get(comparedVersion.version_id)?.preview ?? ""
                    : "")
                }
                className="max-h-96"
              />
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="gap-3 py-4">
                  <CardHeader className="px-4">
                    <CardTitle className="text-base">Original</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4">
                    <div className="bg-muted/30 max-h-80 overflow-auto rounded-lg border p-4 text-sm leading-6 whitespace-pre-wrap">
                      {document.length > 0
                        ? document
                        : (run?.document ?? "No original document available.")}
                    </div>
                  </CardContent>
                </Card>
                <Card className="gap-3 py-4">
                  <CardHeader className="px-4">
                    <CardTitle className="text-base">
                      {comparedVersion ? formatSkillLabel(comparedVersion.skill_name) : "Compared Version"}
                      {comparedVersion?.model_name ? ` · ${comparedVersion.model_name}` : ""}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4">
                    <div className="bg-muted/30 max-h-80 overflow-auto rounded-lg border p-4 text-sm leading-6 whitespace-pre-wrap">
                      {comparedVersion?.output ??
                        (comparedVersion?.version_id
                          ? versionsSummaryBySkill.get(comparedVersion.version_id)?.preview
                          : null) ??
                        "No compared version available."}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        <ScrollArea className="min-h-0 flex-1 pr-3">
          <div className="space-y-4">
            {sortedVersions.length === 0 && (
              <Card className="py-4">
                <CardContent className="text-muted-foreground px-4 text-sm">
                  No versions yet.
                </CardContent>
              </Card>
            )}

            {deferredVersions.map((version, index) => {
              const preview =
                version.output ??
                (version.version_id
                  ? versionsSummaryBySkill.get(version.version_id)?.preview
                  : undefined) ??
                "";
              const isSelected = run?.selected_version_id === version.version_id;
              return (
                <Card
                  key={`${run?.run_id ?? "draft"}-${version.version_id ?? version.skill_name}`}
                  className={cn(
                    "gap-4 py-4",
                    index === 0 && "border-amber-500/35",
                    isSelected && "border-emerald-500/50 bg-emerald-500/5",
                  )}
                >
                  <CardHeader className="px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-2">
                        <CardTitle className="flex items-center gap-2 text-base">
                          {index === 0 && (
                            <MedalIcon className="size-4 text-amber-600" />
                          )}
                          {formatSkillLabel(version.skill_name)}
                          {version.model_name ? ` · ${version.model_name}` : ""}
                        </CardTitle>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">
                            Score {Math.round(version.score * 100)}%
                          </Badge>
                          {run?.review_payload?.suggested_version_id === version.version_id && (
                            <Badge variant="secondary">
                              Suggested
                              {run?.review_payload?.suggested_model_name
                                ? ` · ${run.review_payload.suggested_model_name}`
                                : ""}
                            </Badge>
                          )}
                          {version.model_name && (
                            <Badge variant="secondary">{version.model_name}</Badge>
                          )}
                          {typeof version.token_count === "number" && (
                            <Badge variant="outline">
                              {version.token_count} tokens
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className={cn(
                            "rounded-full border-2",
                            compareVersionId === version.version_id && "border-primary bg-primary/5 text-foreground",
                          )}
                          onClick={() => setCompareVersionId(version.version_id ?? null)}
                          disabled={compareVersionId === version.version_id}
                        >
                          {compareVersionId === version.version_id ? "Comparing" : "Compare"}
                        </Button>
                        {run?.status === "awaiting_selection" && (
                          <Button
                            size="sm"
                            className="rounded-full border-2 border-transparent shadow-sm"
                            onClick={() => void handleSelect(version.version_id ?? version.skill_name)}
                            disabled={selectVersion.isPending}
                          >
                            {selectVersion.isPending &&
                            selectVersion.variables?.versionId === (version.version_id ?? version.skill_name) ? (
                              <Loader2Icon className="size-4 animate-spin" />
                            ) : null}
                            Select This Version
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-full border-2"
                          onClick={() => void handleOpenVersionInEditor(version.version_id ?? version.skill_name)}
                          disabled={createDocument.isPending}
                        >
                          <ArrowUpRightIcon className="size-4" />
                          Open in Editor
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="px-4">
                    <div className="space-y-3">
                      {version.quality_dims && (
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(version.quality_dims).map(
                            ([name, value]) => (
                              <Badge key={name} variant="outline">
                                {name}: {Math.round(value * 100)}%
                              </Badge>
                            ),
                          )}
                        </div>
                      )}
                      <div className="bg-muted/30 max-h-64 overflow-auto rounded-lg border p-4 text-sm leading-6 whitespace-pre-wrap">
                        {preview || "No preview available."}
                      </div>
                    </div>
                  </CardContent>
                  {version.file_path && (
                    <CardFooter className="px-4 pt-0 text-xs text-muted-foreground">
                      {version.file_path}
                    </CardFooter>
                  )}
                </Card>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

export function DocEditDialog({
  disabled,
  mode,
}: {
  disabled?: boolean;
  mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
}) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [studioKey, setStudioKey] = useState(0);
  const [prefillDoc, setPrefillDoc] = useState("");

  useEffect(() => {
    setMounted(true);
  }, []);

  // Listen for cross-component "open with content" events (e.g. from artifact panel)
  useEffect(() => {
    if (!mounted) {
      return;
    }
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ content: string }>).detail;
      setPrefillDoc(detail.content ?? "");
      setStudioKey((k) => k + 1);
      setOpen(true);
    };
    window.addEventListener("maestroflow:doc-edit-open", handler);
    return () => window.removeEventListener("maestroflow:doc-edit-open", handler);
  }, [mounted]);

  if (!mounted) {
    return (
      <Button
        size="sm"
        variant="outline"
        className="rounded-full border-2 px-4"
        disabled
      >
        <FilePenLineIcon className="size-4" />
        Doc Edit
      </Button>
    );
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { setOpen(v); if (!v) setIsFullscreen(false); }}>
      <SheetTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className="rounded-full border-2 px-4"
          disabled={(disabled ?? false) || env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
        >
          <FilePenLineIcon className="size-4" />
          Doc Edit
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        showClose={false}
        className={cn(
          "flex flex-col gap-0 p-0 transition-all duration-200",
          isFullscreen
            ? "!inset-0 !h-screen !w-screen !max-w-none rounded-none"
            : "w-[min(96vw,1680px)] max-w-none",
        )}
      >
        <SheetHeader className="flex shrink-0 flex-row items-center justify-between border-b px-4 py-2">
          <SheetTitle className="flex items-center gap-2 text-base font-semibold">
            <FilePenLineIcon className="size-4" />
            Doc Edit
          </SheetTitle>
          <SheetDescription className="sr-only">
            Parallel document editing studio
          </SheetDescription>
          <div className="flex items-center gap-1">
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => setIsFullscreen((v) => !v)}
              title={isFullscreen ? "Exit fullscreen" : "Expand to fullscreen"}
            >
              {isFullscreen ? (
                <Minimize2Icon className="size-4" />
              ) : (
                <Maximize2Icon className="size-4" />
              )}
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => setOpen(false)}
              title="Close"
            >
              <XIcon className="size-4" />
            </Button>
          </div>
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-hidden">
          <DocEditStudio
            key={studioKey}
            disabled={disabled}
            mode={mode}
            initialDocument={prefillDoc}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}

// Alias kept for backwards compatibility
export { DocEditDialog as DocEditSheet };
