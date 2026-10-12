import React from "react";
import { Cloud, ArrowRight, HardDrive } from "lucide-react";
import { motion } from "framer-motion";
import type { TaskState } from "@/types/task";
import { formatBytes, formatSpeed, formatEta } from "@/lib/format";
import { AnimatedTicker } from "./AnimatedTicker";

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

  // State-specific bar styling: uploading shifts color to cyan/sky to mark phase transition
  let fillClasses = "bg-accent-grad";
  if (state === "completed") fillClasses = "bg-success";
  else if (state === "failed") fillClasses = "bg-danger";
  else if (state === "paused") fillClasses = "bg-warning";
  else if (state === "cancelled") fillClasses = "bg-border";
  else if (state === "uploading") fillClasses = "bg-gradient-to-r from-accent-2 to-sky-400";

  return (
    <div className={`w-full flex flex-col gap-2 ${className}`}>
      {/* Track bar */}
      <div className="relative w-full h-2 rounded-full bg-surface border border-border overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ease-out rounded-full relative overflow-hidden ${fillClasses}`}
          style={{ width: `${percent}%` }}
        >
          {isAnimated && (
            <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent_0%,rgba(255,255,255,0.28)_50%,transparent_100%)] animate-sheen will-change-transform" />
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
              <span className="text-text font-medium">
                <AnimatedTicker value={formatSpeed(speedBps)} />
              </span>
            </>
          )}

          {state === "downloading" && etaSeconds && etaSeconds > 0 && (
            <>
              <span className="text-border">•</span>
              <span>
                <AnimatedTicker value={formatEta(etaSeconds)} />
              </span>
            </>
          )}

          {state === "uploading" && (
            <>
              <span className="text-border">•</span>
              <span className="inline-flex items-center gap-1.5 text-accent-2 font-medium">
                <span className="flex items-center gap-0.5" data-testid="cloud-drive-path">
                  <Cloud className="w-3.5 h-3.5" />
                  <motion.span
                    animate={{ x: [0, 2, 0], opacity: [0.6, 1, 0.6] }}
                    transition={{ repeat: Infinity, duration: 1.2, ease: "easeInOut" }}
                    className="inline-flex"
                  >
                    <ArrowRight className="w-3 h-3 text-accent-2" />
                  </motion.span>
                  <HardDrive className="w-3.5 h-3.5 text-accent-2" />
                </span>
                <span>Uploading to Drive...</span>
              </span>
            </>
          )}
        </div>

        <div className="font-semibold text-text">
          <AnimatedTicker value={`${percent.toFixed(1)}%`} />
        </div>
      </div>
    </div>
  );
};
