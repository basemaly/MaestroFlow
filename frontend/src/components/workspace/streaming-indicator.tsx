import { cn } from "@/lib/utils";

export function StreamingIndicator({
  className,
  size = "normal",
}: {
  className?: string;
  size?: "normal" | "sm";
}) {
  // Wave bars — each bar has a different height and animation delay to simulate an audio waveform
  const bars = [
    { delay: "0ms",   height: size === "sm" ? "h-2" : "h-3" },
    { delay: "80ms",  height: size === "sm" ? "h-3.5" : "h-5" },
    { delay: "160ms", height: size === "sm" ? "h-2.5" : "h-4" },
    { delay: "240ms", height: size === "sm" ? "h-4" : "h-6" },
    { delay: "120ms", height: size === "sm" ? "h-2" : "h-3" },
  ];
  const barWidth = size === "sm" ? "w-0.5" : "w-1";

  return (
    <div
      className={cn("flex items-end gap-0.5", className)}
      role="status"
      aria-label="Generating response"
    >
      {bars.map((bar, i) => (
        <span
          key={i}
          className={cn(
            barWidth,
            bar.height,
            "rounded-full bg-amber-500/70 origin-bottom",
          )}
          style={{
            animation: `streaming-wave 900ms ease-in-out infinite alternate`,
            animationDelay: bar.delay,
          }}
        />
      ))}
      <style>{`
        @keyframes streaming-wave {
          from { transform: scaleY(0.25); opacity: 0.5; }
          to   { transform: scaleY(1);    opacity: 1;   }
        }
      `}</style>
    </div>
  );
}
