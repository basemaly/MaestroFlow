"use client";

export function MusicalClefLoader() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <svg
        width="64"
        height="64"
        viewBox="0 0 64 64"
        className="animate-pulse"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Treble Clef */}
        <defs>
          <style>{`
            @keyframes clef-float {
              0%, 100% { transform: translateY(0px); }
              50% { transform: translateY(-8px); }
            }
            .clef-symbol {
              animation: clef-float 2s ease-in-out infinite;
            }
          `}</style>
        </defs>

        <g className="clef-symbol" stroke="currentColor" strokeWidth="1.5" fill="none">
          {/* Clef curves and details */}
          <circle cx="32" cy="20" r="6" fill="currentColor" />
          <path d="M 26 26 Q 26 35 32 35 Q 38 35 38 26" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M 28 38 Q 28 45 32 48 Q 36 45 36 38" strokeLinecap="round" strokeLinejoin="round" />
        </g>

        {/* Decorative musical notes floating */}
        <g className="animate-bounce" style={{ animationDelay: '0.1s' }}>
          <circle cx="48" cy="24" r="1.5" fill="currentColor" />
          <line x1="48" y1="24" x2="48" y2="14" stroke="currentColor" strokeWidth="1" />
        </g>

        <g className="animate-bounce" style={{ animationDelay: '0.2s' }}>
          <circle cx="16" cy="32" r="1.5" fill="currentColor" />
          <line x1="16" y1="32" x2="16" y2="22" stroke="currentColor" strokeWidth="1" />
        </g>
      </svg>

      <div className="text-center">
        <p className="text-sm font-medium text-foreground">Loading your workspace</p>
        <div className="mt-2 flex justify-center gap-1">
          <div className="size-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '0s' }} />
          <div className="size-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '0.1s' }} />
          <div className="size-2 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: '0.2s' }} />
        </div>
      </div>
    </div>
  );
}
