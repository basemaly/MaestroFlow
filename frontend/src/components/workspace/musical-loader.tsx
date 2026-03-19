"use client";

export function MusicalClefLoader() {
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-12">
      {/* Animated treble clef symbol with musical glow */}
      <div className="relative">
        {/* Glow effect */}
        <div className="absolute inset-0 -m-4 rounded-full bg-gradient-to-r from-amber-500/20 via-amber-400/10 to-transparent blur-2xl animate-pulse" />

        {/* Main clef symbol */}
        <svg
          width="80"
          height="80"
          viewBox="0 0 64 64"
          className="relative z-10 text-amber-500"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <style>{`
              @keyframes clef-float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
              }
              .clef-symbol {
                animation: clef-float 2.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
              }
              @keyframes spin-slow {
                0%, 100% { transform: rotate(0deg); }
                50% { transform: rotate(2deg); }
              }
              .clef-spin {
                animation: spin-slow 3s ease-in-out infinite;
              }
            `}</style>
          </defs>

          <g className="clef-symbol clef-spin" stroke="currentColor" strokeWidth="1.5" fill="none">
            {/* Clef curves and details */}
            <circle cx="32" cy="20" r="6" fill="currentColor" opacity="0.8" />
            <path d="M 26 26 Q 26 35 32 35 Q 38 35 38 26" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M 28 38 Q 28 45 32 48 Q 36 45 36 38" strokeLinecap="round" strokeLinejoin="round" />
          </g>

          {/* Decorative musical notes floating around clef */}
          <g className="animate-bounce" style={{ animationDelay: "0.1s", animationDuration: "1.4s" }}>
            <circle cx="48" cy="24" r="1.5" fill="currentColor" opacity="0.7" />
            <line x1="48" y1="24" x2="48" y2="14" stroke="currentColor" strokeWidth="1" opacity="0.6" />
          </g>

          <g className="animate-bounce" style={{ animationDelay: "0.3s", animationDuration: "1.4s" }}>
            <circle cx="16" cy="32" r="1.5" fill="currentColor" opacity="0.6" />
            <line x1="16" y1="32" x2="16" y2="22" stroke="currentColor" strokeWidth="1" opacity="0.5" />
          </g>
        </svg>
      </div>

      {/* Status text */}
      <div className="text-center">
        <p className="text-sm font-medium text-foreground/80">Harmonizing your workspace</p>
        <div className="mt-3 flex justify-center gap-2">
          <div
            className="size-2 rounded-full bg-amber-500/60 animate-bounce"
            style={{ animationDelay: "0s", animationDuration: "1.4s" }}
          />
          <div
            className="size-2 rounded-full bg-amber-500/60 animate-bounce"
            style={{ animationDelay: "0.15s", animationDuration: "1.4s" }}
          />
          <div
            className="size-2 rounded-full bg-amber-500/60 animate-bounce"
            style={{ animationDelay: "0.3s", animationDuration: "1.4s" }}
          />
        </div>
      </div>
    </div>
  );
}
