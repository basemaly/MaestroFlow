"use client";

import {
  ActivityIcon,
  ArrowRightIcon,
  FileTextIcon,
  HeartPulseIcon,
  RadioTowerIcon,
  SearchIcon,
  WavesIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDiagnosticsComponentLogs, useDiagnosticsEvents, useDiagnosticsLogComponents, useDiagnosticsOverview, useDiagnosticsRequests, useDiagnosticsTraces } from "@/core/diagnostics/hooks";
import type { DiagnosticsEventEntry, DiagnosticsLogLine, DiagnosticsRequestEntry, DiagnosticsTraceEntry } from "@/core/diagnostics/types";
import { cn } from "@/lib/utils";

const sections = [
  { key: "overview", label: "Overview", href: "/workspace/diagnostics", icon: HeartPulseIcon },
  { key: "logs", label: "Logs", href: "/workspace/diagnostics/logs", icon: FileTextIcon },
  { key: "requests", label: "Requests", href: "/workspace/diagnostics/requests", icon: RadioTowerIcon },
  { key: "traces", label: "Traces", href: "/workspace/diagnostics/traces", icon: WavesIcon },
  { key: "events", label: "Events", href: "/workspace/diagnostics/events", icon: ActivityIcon },
] as const;

function formatTimestamp(value?: string | null): string {
  if (!value) return "Unknown";
  try {
    return new Date(value).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return value;
  }
}

function statusTone(state: string): string {
  if (state === "healthy") return "text-emerald-300 border-emerald-500/30 bg-emerald-500/10";
  if (state === "disabled") return "text-slate-300 border-slate-500/30 bg-slate-500/10";
  if (state === "degraded") return "text-amber-300 border-amber-500/30 bg-amber-500/10";
  return "text-red-300 border-red-500/30 bg-red-500/10";
}

function DiagnosticsNav({ active }: { active: DiagnosticsSection }) {
  return (
    <div className="flex flex-wrap gap-2">
      {sections.map(({ key, label, href, icon: Icon }) => (
        <Button
          key={key}
          asChild
          variant={active === key ? "secondary" : "outline"}
          className="rounded-full"
        >
          <Link href={href}>
            <Icon className="size-4" />
            {label}
          </Link>
        </Button>
      ))}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="text-muted-foreground rounded-xl border border-dashed p-4 text-sm">
      <div className="font-medium text-foreground">{title}</div>
      <div className="mt-1">{body}</div>
    </div>
  );
}

function RequestRow({ item }: { item: DiagnosticsRequestEntry }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/70 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">
          {item.method} {item.path}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {item.status ? <Badge variant="outline" className="rounded-full">{item.status}</Badge> : null}
          <Badge variant="outline" className="rounded-full">{item.kind}</Badge>
        </div>
      </div>
      <div className="text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
        <span>{formatTimestamp(item.timestamp)}</span>
        {item.request_id ? <span>Request {item.request_id}</span> : null}
        {item.trace_id ? <span>Trace {item.trace_id}</span> : null}
        {typeof item.duration_ms === "number" ? <span>{item.duration_ms.toFixed(2)} ms</span> : null}
      </div>
    </div>
  );
}

function TraceRow({ item }: { item: DiagnosticsTraceEntry }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/70 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">{item.trace_id}</div>
        <Badge variant="outline" className="rounded-full">
          {item.request_count} request{item.request_count === 1 ? "" : "s"}
        </Badge>
      </div>
      <div className="text-muted-foreground mt-2 text-xs">
        Last seen {formatTimestamp(item.last_seen_at)}
        {item.latest_request_id ? ` · Latest request ${item.latest_request_id}` : ""}
      </div>
      {item.paths.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {item.paths.slice(0, 4).map((path) => (
            <Badge key={path} variant="outline" className="rounded-full text-[11px]">
              {path}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function EventRow({ item }: { item: DiagnosticsEventEntry }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/70 p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">{item.title}</div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="rounded-full">{item.event_kind}</Badge>
          <Badge variant="outline" className="rounded-full">{item.status}</Badge>
        </div>
      </div>
      <div className="text-muted-foreground mt-2">{item.summary}</div>
      <div className="text-muted-foreground mt-1 text-xs">{formatTimestamp(item.timestamp)}</div>
    </div>
  );
}

function LogLineRow({ line }: { line: DiagnosticsLogLine }) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/70 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>{formatTimestamp(line.timestamp)}</span>
        {line.level ? <Badge variant="outline" className="rounded-full">{line.level}</Badge> : null}
        {line.request_id ? <span>Request {line.request_id}</span> : null}
        {line.trace_id ? <span>Trace {line.trace_id}</span> : null}
      </div>
      <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-foreground">
        {line.message ?? line.raw}
      </pre>
    </div>
  );
}

export type DiagnosticsSection = "overview" | "logs" | "requests" | "traces" | "events";

export function DiagnosticsPageClient({ section }: { section: DiagnosticsSection }) {
  const overviewQuery = useDiagnosticsOverview(section === "overview");
  const logComponentsQuery = useDiagnosticsLogComponents(section === "logs");
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [logFilter, setLogFilter] = useState("");
  const [pathFilter, setPathFilter] = useState("");
  const [traceFilter, setTraceFilter] = useState("");
  const logComponents = useMemo(
    () => logComponentsQuery.data?.components ?? [],
    [logComponentsQuery.data?.components],
  );

  const activeComponentId = useMemo(() => {
    if (selectedComponentId) return selectedComponentId;
    return logComponents[0]?.component_id ?? null;
  }, [logComponents, selectedComponentId]);

  const logsQuery = useDiagnosticsComponentLogs(
    section === "logs" ? activeComponentId : null,
    120,
    logFilter.trim() || undefined,
    section === "logs",
  );
  const requestsQuery = useDiagnosticsRequests(
    section === "requests" ? { limit: 120, pathContains: pathFilter.trim() || undefined } : undefined,
    section === "requests",
  );
  const tracesQuery = useDiagnosticsTraces(
    section === "traces" ? { limit: 120, traceId: traceFilter.trim() || undefined } : undefined,
    section === "traces",
  );
  const eventsQuery = useDiagnosticsEvents(
    section === "events" ? { limit: 120 } : undefined,
    section === "events",
  );

  return (
    <div className="flex size-full flex-col bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.08),transparent_20%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.05),transparent_18%)]">
      <div className="border-b border-border/70 px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
              Diagnostics
            </div>
            <div className="mt-2 text-2xl font-semibold tracking-tight">Logs, requests, traces, and operational events</div>
            <div className="mt-2 text-sm text-muted-foreground">
              Use Diagnostics to inspect request-correlated runtime signals without dragging heavy inspection views into Executive.
            </div>
          </div>
          <Button asChild variant="outline" className="rounded-full">
            <Link href="/workspace/executive">
              Back to Executive
              <ArrowRightIcon className="size-4" />
            </Link>
          </Button>
        </div>
        <div className="mt-4">
          <DiagnosticsNav active={section} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {section === "overview" ? (
          <div className="space-y-6">
            <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {Object.entries(overviewQuery.data?.status.summary ?? {}).map(([label, count]) => (
                <Card key={label} className="border-border/60 bg-background/70 py-3">
                  <CardHeader className="px-4 pb-1">
                    <CardDescription className="text-[11px] uppercase tracking-[0.12em]">{label}</CardDescription>
                    <CardTitle className="text-2xl">{count}</CardTitle>
                  </CardHeader>
                </Card>
              ))}
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <Card className="border-border/60 py-4">
                <CardHeader className="px-4">
                  <CardTitle className="text-base">System status</CardTitle>
                  <CardDescription>Component health and the most recent warnings.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 px-4">
                  {(overviewQuery.data?.status.components ?? []).map((component) => (
                    <div key={component.component_id} className="rounded-xl border border-border/70 bg-background/70 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-medium">{component.label}</div>
                        <Badge variant="outline" className={cn("rounded-full", statusTone(component.state))}>
                          {component.state}
                        </Badge>
                      </div>
                      <div className="text-muted-foreground mt-2 text-sm">{component.summary}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="border-border/60 py-4">
                <CardHeader className="px-4">
                  <CardTitle className="text-base">Quick links</CardTitle>
                  <CardDescription>Jump straight into the heavier inspection views only when needed.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 px-4 md:grid-cols-2">
                  {[
                    { href: "/workspace/diagnostics/logs", title: "Component logs", body: "Tail bounded logs per component." },
                    { href: "/workspace/diagnostics/requests", title: "Request timeline", body: "Inspect request IDs, paths, statuses, and durations." },
                    { href: "/workspace/diagnostics/traces", title: "Trace groups", body: "See long-running actions grouped by trace ID." },
                    { href: "/workspace/diagnostics/events", title: "Operational events", body: "Approvals and audit events without the Executive page clutter." },
                  ].map((item) => (
                    <Link key={item.href} href={item.href} className="rounded-xl border border-border/70 bg-background/70 p-4 transition-colors hover:bg-accent/40">
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{item.body}</div>
                    </Link>
                  ))}
                </CardContent>
              </Card>
            </section>
          </div>
        ) : null}

        {section === "logs" ? (
          <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
            <Card className="border-border/60 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Components</CardTitle>
                <CardDescription>Select a component log. Nothing live-tails unless you refresh.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 px-4">
                {logComponents.map((component) => (
                  <button
                    key={component.component_id}
                    className={cn(
                      "w-full rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                      activeComponentId === component.component_id ? "border-primary/40 bg-primary/10" : "border-border/70 bg-background/70",
                    )}
                    onClick={() => setSelectedComponentId(component.component_id)}
                  >
                    <div className="font-medium">{component.label}</div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      {component.exists ? "Available" : "Missing"} · {formatTimestamp(component.updated_at)}
                    </div>
                  </button>
                ))}
              </CardContent>
            </Card>
            <Card className="border-border/60 py-4">
              <CardHeader className="px-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">Log viewer</CardTitle>
                    <CardDescription>Bounded recent lines only, with optional text filtering.</CardDescription>
                  </div>
                  <div className="w-full max-w-xs">
                    <Input
                      value={logFilter}
                      onChange={(event) => setLogFilter(event.target.value)}
                      placeholder="Filter text"
                    />
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 px-4">
                {!logsQuery.data?.lines?.length ? (
                  <EmptyState title="No log lines yet" body="Try another component or clear the filter." />
                ) : (
                  logsQuery.data.lines.map((line, index) => <LogLineRow key={`${line.timestamp ?? "line"}-${index}`} line={line} />)
                )}
              </CardContent>
            </Card>
          </div>
        ) : null}

        {section === "requests" ? (
          <Card className="border-border/60 py-4">
            <CardHeader className="px-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Request timeline</CardTitle>
                  <CardDescription>Recent gateway requests with request IDs, trace IDs, and durations.</CardDescription>
                </div>
                <div className="relative w-full max-w-xs">
                  <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    value={pathFilter}
                    onChange={(event) => setPathFilter(event.target.value)}
                    placeholder="Filter by path"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 px-4">
              {!requestsQuery.data?.items?.length ? (
                <EmptyState title="No matching requests" body="Once request-complete logs are flowing, they appear here." />
              ) : (
                requestsQuery.data.items.map((item) => <RequestRow key={`${item.request_id ?? item.message}-${item.timestamp ?? ""}`} item={item} />)
              )}
            </CardContent>
          </Card>
        ) : null}

        {section === "traces" ? (
          <Card className="border-border/60 py-4">
            <CardHeader className="px-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Trace groups</CardTitle>
                  <CardDescription>Trace-centric view for long-running actions such as Executive runs and document transforms.</CardDescription>
                </div>
                <div className="w-full max-w-xs">
                  <Input
                    value={traceFilter}
                    onChange={(event) => setTraceFilter(event.target.value)}
                    placeholder="Filter by trace ID"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 px-4">
              {!tracesQuery.data?.items?.length ? (
                <EmptyState title="No recent traces" body="Trace groups appear here when actions include a trace ID." />
              ) : (
                tracesQuery.data.items.map((item) => <TraceRow key={item.trace_id} item={item} />)
              )}
            </CardContent>
          </Card>
        ) : null}

        {section === "events" ? (
          <Card className="border-border/60 py-4">
            <CardHeader className="px-4">
              <CardTitle className="text-base">Operational events</CardTitle>
              <CardDescription>Approvals and audit history moved out of Executive so the control plane stays focused.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 px-4">
              {!eventsQuery.data?.items?.length ? (
                <EmptyState title="No recent events" body="Audit entries and approvals show up here once activity occurs." />
              ) : (
                eventsQuery.data.items.map((item) => <EventRow key={`${item.event_kind}-${item.event_id}`} item={item} />)
              )}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
