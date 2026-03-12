"use client";

import {
  CheckCircle2Icon,
  FilePenLineIcon,
  Loader2Icon,
  MedalIcon,
  PaperclipIcon,
  SparklesIcon,
} from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  useSelectDocEditVersion,
  useStartDocEditRun,
  useUploadDocEditFile,
} from "@/core/doc-editing/hooks";
import type { DocEditRun } from "@/core/doc-editing/types";
import { env } from "@/env";
import { cn } from "@/lib/utils";

type ModelPreference = "local" | "fast" | "strong";

const SKILL_OPTIONS = [
  { value: "writing-refiner", label: "Writing Refiner" },
  { value: "argument-critic", label: "Argument Critic" },
  { value: "humanizer", label: "Humanizer" },
] as const;
const DEFAULT_SKILLS = ["writing-refiner", "argument-critic"];

function resolveModelPreference(
  mode: "flash" | "thinking" | "pro" | "ultra" | undefined,
): ModelPreference {
  if (mode === "pro" || mode === "ultra") {
    return "strong";
  }
  return "fast";
}

export function DocEditStudio({
  disabled,
  mode,
  initialRun,
  embedded = false,
}: {
  disabled?: boolean;
  mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
  initialRun?: DocEditRun | null;
  embedded?: boolean;
}) {
  const [document, setDocument] = useState(initialRun?.document ?? "");
  const [skills, setSkills] = useState<string[]>(
    initialRun?.versions?.map((version) => version.skill_name) ??
      DEFAULT_SKILLS,
  );
  const [modelPreference, setModelPreference] = useState<ModelPreference>(
    resolveModelPreference(mode),
  );
  const [tokenBudget, setTokenBudget] = useState("4000");
  const [run, setRun] = useState<DocEditRun | null>(initialRun ?? null);
  const [compareSkill, setCompareSkill] = useState<string | null>(
    initialRun?.selected_skill ??
      initialRun?.versions?.[0]?.skill_name ??
      null,
  );
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const startRun = useStartDocEditRun();
  const selectVersion = useSelectDocEditVersion();
  const uploadFile = useUploadDocEditFile();

  useEffect(() => {
    if (!initialRun) {
      return;
    }
    setRun(initialRun);
    setDocument(initialRun.document ?? "");
    if (initialRun.versions.length > 0) {
      setCompareSkill(
        initialRun.selected_skill ?? initialRun.versions[0]?.skill_name ?? null,
      );
      setSkills(initialRun.versions.map((version) => version.skill_name));
    }
  }, [initialRun]);

  useEffect(() => {
    if (run || startRun.isPending || selectVersion.isPending) {
      return;
    }
    setModelPreference(resolveModelPreference(mode));
  }, [mode, run, selectVersion.isPending, startRun.isPending]);

  const wordCount = document.trim().split(/\s+/).filter(Boolean).length;
  const runTitle = run?.title ?? "Parallel Document Editing";
  const invalidBudget =
    tokenBudget.trim().length > 0 &&
    Number.parseInt(tokenBudget, 10) < 250;

  const sortedVersions = useMemo(() => run?.versions ?? [], [run]);
  const deferredVersions = useDeferredValue(sortedVersions);
  const versionsSummaryBySkill = useMemo(
    () =>
      new Map(
        run?.review_payload?.versions_summary?.map((item) => [item.skill_name, item]) ?? [],
      ),
    [run?.review_payload?.versions_summary],
  );
  const comparedVersion = useMemo(
    () =>
      deferredVersions.find((version) => version.skill_name === compareSkill) ??
      deferredVersions[0] ??
      null,
    [compareSkill, deferredVersions],
  );
  const canSubmit =
    document.trim().length > 0 &&
    skills.length > 0 &&
    !(disabled ?? false) &&
    !invalidBudget &&
    !uploadFile.isPending &&
    !selectVersion.isPending;

  useEffect(() => {
    if (deferredVersions.length === 0) {
      if (compareSkill !== null) {
        setCompareSkill(null);
      }
      return;
    }
    if (!compareSkill || !deferredVersions.some((version) => version.skill_name === compareSkill)) {
      setCompareSkill(run?.selected_skill ?? deferredVersions[0]?.skill_name ?? null);
    }
  }, [compareSkill, deferredVersions, run?.selected_skill]);

  function resetStudio() {
    setRun(null);
    setDocument("");
    setCompareSkill(null);
    setTokenBudget("4000");
    setSkills(DEFAULT_SKILLS);
    setModelPreference(resolveModelPreference(mode));
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
        model_preference: modelPreference,
        token_budget: Number.isNaN(parsedBudget) ? 4000 : parsedBudget,
      });
      setRun(nextRun);
      setCompareSkill(
        nextRun.selected_skill ?? nextRun.versions[0]?.skill_name ?? null,
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

  async function handleSelect(skillName: string) {
    if (!run) {
      return;
    }
    try {
      const nextRun = await selectVersion.mutateAsync({
        runId: run.run_id,
        skillName,
      });
      setRun(nextRun);
      setCompareSkill(skillName);
      toast.success(`Selected ${skillName} as the final version`);
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

  return (
    <div className={cn("grid h-full min-h-[70vh] grid-cols-1 lg:grid-cols-[1.05fr_1.25fr]", embedded && "min-h-0")}>
      <div className={cn("border-border/70 bg-muted/20 p-6", !embedded && "border-r")}>
        <DialogHeader className="mb-6">
          <DialogTitle className="flex items-center gap-2">
            <SparklesIcon className="size-4" />
            {runTitle}
          </DialogTitle>
          <DialogDescription>
            Paste markdown or upload a supported file, run multiple editorial skills in parallel, then choose the winner.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="space-y-2">
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

          <div className="space-y-2">
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
                  className="rounded-md"
                >
                  {skill.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Model Mode</div>
            <ToggleGroup
              type="single"
              variant="outline"
              value={modelPreference}
              onValueChange={(value) => {
                if (value === "local" || value === "fast" || value === "strong") {
                  setModelPreference(value);
                }
              }}
            >
              <ToggleGroupItem value="local">Local</ToggleGroupItem>
              <ToggleGroupItem value="fast">Fast</ToggleGroupItem>
              <ToggleGroupItem value="strong">Strong</ToggleGroupItem>
            </ToggleGroup>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Token Budget</div>
            <Textarea
              className="min-h-0 resize-none bg-background"
              rows={1}
              value={tokenBudget}
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

          <div className="flex gap-2">
            <Button onClick={handleRun} disabled={!canSubmit || startRun.isPending}>
              {startRun.isPending ? (
                <Loader2Icon className="size-4 animate-spin" />
              ) : (
                <SparklesIcon className="size-4" />
              )}
              Run Versions
            </Button>
            <Button
              variant="ghost"
              onClick={resetStudio}
              disabled={startRun.isPending || selectVersion.isPending || uploadFile.isPending}
            >
              Reset
            </Button>
          </div>
        </div>
      </div>

      <div className="bg-background p-6">
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
              value={compareSkill ?? undefined}
              onValueChange={(value) => setCompareSkill(value || null)}
            >
              {sortedVersions.map((version) => (
                <ToggleGroupItem key={version.skill_name} value={version.skill_name}>
                  {version.skill_name}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}

        {(document || comparedVersion) && (
          <div className="mb-6 grid gap-4 lg:grid-cols-2">
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
                  {comparedVersion?.skill_name ?? "Compared Version"}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4">
                <div className="bg-muted/30 max-h-80 overflow-auto rounded-lg border p-4 text-sm leading-6 whitespace-pre-wrap">
                  {comparedVersion?.output ??
                    (comparedVersion?.skill_name
                      ? versionsSummaryBySkill.get(comparedVersion.skill_name)?.preview
                      : null) ??
                    "No compared version available."}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <ScrollArea className={cn("pr-3", embedded ? "h-[32rem]" : "h-[calc(70vh-24rem)]")}>
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
                versionsSummaryBySkill.get(version.skill_name)?.preview ??
                "";
              const isSelected = run?.selected_skill === version.skill_name;
              return (
                <Card
                  key={`${run?.run_id ?? "draft"}-${version.skill_name}`}
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
                          {version.skill_name}
                        </CardTitle>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">
                            Score {Math.round(version.score * 100)}%
                          </Badge>
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
                          onClick={() => setCompareSkill(version.skill_name)}
                        >
                          Compare
                        </Button>
                        {run?.status === "awaiting_selection" && (
                          <Button
                            size="sm"
                            onClick={() => void handleSelect(version.skill_name)}
                            disabled={selectVersion.isPending}
                          >
                            {selectVersion.isPending &&
                            selectVersion.variables?.skillName === version.skill_name ? (
                              <Loader2Icon className="size-4 animate-spin" />
                            ) : null}
                            Select This Version
                          </Button>
                        )}
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
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          disabled={(disabled ?? false) || env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
        >
          <FilePenLineIcon className="size-4" />
          Doc Edit
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-6xl overflow-hidden p-0">
        <DocEditStudio disabled={disabled} mode={mode} />
      </DialogContent>
    </Dialog>
  );
}
