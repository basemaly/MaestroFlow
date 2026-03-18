import { ArrowRightIcon, BotIcon, ChartLineIcon, FlaskConicalIcon, WrenchIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const capabilities = [
  {
    title: "Read experiment metrics",
    description:
      "Inspect the latest EvoBranch run metrics, including validation loss, VRAM usage, and status.",
    icon: ChartLineIcon,
  },
  {
    title: "Mutate training code",
    description:
      "Safely overwrite the sandboxed training script with a new architecture hypothesis or training change.",
    icon: WrenchIcon,
  },
  {
    title: "Trigger a training cycle",
    description:
      "Run the next training cycle inside the dedicated Autoresearcher sandbox and collect the outcome.",
    icon: FlaskConicalIcon,
  },
];

export default function AutoresearchPage() {
  return (
    <div className="flex size-full flex-col">
      <div className="border-b px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
              <FlaskConicalIcon className="h-3.5 w-3.5" />
              Experimental ML workspace
            </div>
            <h1 className="text-xl font-semibold">Autoresearcher</h1>
            <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
              A dedicated workspace for the EvoBranch training loop. This is separate from Executive and separate from
              general agent presets so the ML automation surface stays explicit.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/workspace/chats/new">
                Open a fresh chat
                <ArrowRightIcon className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild>
              <Link href="/workspace/agents">
                View agent presets
                <BotIcon className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid w-full max-w-6xl gap-6 xl:grid-cols-[1.35fr_0.95fr]">
          <section className="rounded-3xl border border-border/60 bg-card/70 p-6 shadow-sm">
            <h2 className="text-base font-semibold">What lives here</h2>
            <p className="text-muted-foreground mt-2 text-sm leading-6">
              Autoresearcher is the ML experiment loop that reads run metrics, mutates the training code, and triggers
              the next training cycle inside a dedicated sandbox. It is intentionally isolated from Executive so
              operational controls and experiment controls do not blur together.
            </p>

            <div className="mt-5 grid gap-3">
              {capabilities.map(({ title, description, icon: Icon }) => (
                <div
                  key={title}
                  className="flex items-start gap-4 rounded-2xl border border-border/60 bg-background/70 p-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium">{title}</h3>
                    <p className="text-muted-foreground mt-1 text-sm leading-6">{description}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-3xl border border-border/60 bg-card/70 p-6 shadow-sm">
              <h2 className="text-base font-semibold">Current workflow</h2>
              <ol className="text-muted-foreground mt-3 space-y-3 text-sm leading-6">
                <li>1. Read the latest experiment metrics.</li>
                <li>2. Form a hypothesis about the next training change.</li>
                <li>3. Mutate the sandboxed training code.</li>
                <li>4. Trigger the next training cycle and inspect the result.</li>
              </ol>
            </section>

            <section className="rounded-3xl border border-amber-500/25 bg-amber-500/10 p-6 shadow-sm">
              <h2 className="text-base font-semibold text-amber-900 dark:text-amber-100">Deliberate separation</h2>
              <p className="mt-2 text-sm leading-6 text-amber-900/85 dark:text-amber-100/90">
                Executive remains the control plane for MaestroFlow. Autoresearcher is a specialized experiment loop.
                They can coordinate later, but they should not share a menu label, icon, or mental model.
              </p>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
