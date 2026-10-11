import React from "react";
import type { TaskState } from "@/types/task";
import { formatBytes, formatSpeed, formatEta } from "@/lib/format";

interface ProgressBarProps {
  progress: number; // 0.0 to 1.0
  state: TaskState;
  speedBps?: number;
  downloadedBytes?: number;
  totalBytes?: number;
  etaSeconds?: number | null;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  state,
  speedBps = 0,
  downloadedBytes = 0,
  totalBytes = 0,
  etaSeconds = null,
  className = "",
}) => {
  const percent = Math.min(100, Math.max(0, Math.round(progress * 1000) / 10));
  const isAnimated = state === "downloading" || state === "uploading";

  // State-specific bar styling
  let fillClasses = "bg-accent-grad";
  if (state === "completed") fillClasses = "bg-success";
  else if (state === "failed") fillClasses = "bg-danger";
  else if (state === "paused") fillClasses = "bg-warning";
  else if (state === "cancelled") fillClasses = "bg-border";

  return (
    <div className={`w-full flex flex-col gap-2 ${className}`}>
      {/* Track bar */}
      <div className="relative w-full h-2 rounded-full bg-surface border border-border overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ease-out rounded-full relative ${fillClasses}`}
          style={{ width: `${percent}%` }}
        >
          {isAnimated && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
          )}
        </div>
      </div>

      {/* Meta ticker: bytes, speed, ETA, percent in font-mono tabular-nums */}
      <div className="flex items-center justify-between text-xs font-mono tabular-nums text-text-muted">
        <div className="flex items-center gap-2">
          {totalBytes > 0 ? (
            <span>
              {formatBytes(downloadedBytes)} / {formatBytes(totalBytes)}
            </span>
          ) : (
            <span>{formatBytes(downloadedBytes)}</span>
          )}

          {state === "downloading" && speedBps > 0 && (
            <>
              <span className="text-border">•</span>
              <span className="text-text font-medium">{formatSpeed(speedBps)}</span>
            </>
          )}

          {state === "downloading" && etaSeconds && etaSeconds > 0 && (
            <>
              <span className="text-border">•</span>
              <span>{formatEta(etaSeconds)}</span>
            </>
          )}

          {state === "uploading" && (
            <>
              <span className="text-border">•</span>
              <span className="text-accent-2 font-medium">Uploading to Drive...</span>
            </>
          )}
        </div>

        <div className="font-semibold text-text">{percent.toFixed(1)}%</div>
      </div>
    </div>
  );
};
