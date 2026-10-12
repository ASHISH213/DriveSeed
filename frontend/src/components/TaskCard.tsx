import React, { useState } from "react";
import {
  Magnet,
  Link as LinkIcon,
  Pause,
  Play,
  X,
  CheckCircle2,
  AlertTriangle,
  CloudUpload,
  Clock,
  Loader2,
  FolderDown,
  RotateCcw,
} from "lucide-react";
import { motion } from "framer-motion";
import type { Task } from "@/types/task";
import { ProgressBar } from "./ProgressBar";
import { useMotionPreset } from "@/lib/motion";

interface TaskCardProps {
  task: Task;
  onPause?: (taskId: string) => Promise<unknown>;
  onResume?: (taskId: string) => Promise<unknown>;
  onCancel?: (taskId: string) => Promise<unknown>;
  onRetry?: (taskId: string) => Promise<unknown>;
  onSelectFiles?: (task: Task) => void;
}

export const TaskCard = React.forwardRef<HTMLDivElement, TaskCardProps>(
  ({ task, onPause, onResume, onCancel, onRetry, onSelectFiles }, ref) => {
    const [isActing, setIsActing] = useState(false);
    const { cardHover } = useMotionPreset();

  const handleAction = async (action: () => Promise<unknown>) => {
    if (isActing) return;
    setIsActing(true);
    try {
      await action();
    } catch (err) {
      console.error("Task action failed:", err);
    } finally {
      setIsActing(false);
    }
  };

  const isMagnet = task.source_type === "magnet";
  const canPause = (task.state === "downloading" || task.state === "queued") && !!onPause;
  const canResume = task.state === "paused" && !!onResume;
  const canCancel =
    (task.state === "downloading" ||
      task.state === "queued" ||
      task.state === "paused" ||
      task.state === "uploading" ||
      task.state === "awaiting_selection" ||
      task.state === "fetching_metadata") &&
    !!onCancel;

  // Status Badge Rendering
  const renderBadge = () => {
    switch (task.state) {
      case "awaiting_selection":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-accent-1/20 text-accent-1 border border-accent-1/40">
            <FolderDown className="w-3.5 h-3.5" />
            Awaiting Selection
          </span>
        );
      case "fetching_metadata":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-accent-2/15 text-accent-2 border border-accent-2/30">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Fetching Metadata
          </span>
        );
      case "downloading":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-accent-1/15 text-accent-1 border border-accent-1/30">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-1 animate-pulse" />
            Downloading
          </span>
        );
      case "uploading":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-accent-2/15 text-accent-2 border border-accent-2/30">
            <CloudUpload className="w-3.5 h-3.5 animate-bounce" />
            Uploading to Drive
          </span>
        );
      case "completed":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-success/15 text-success border border-success/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Completed
          </span>
        );
      case "paused":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-warning/15 text-warning border border-warning/30">
            <Pause className="w-3.5 h-3.5" />
            Paused
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-danger/15 text-danger border border-danger/30">
            <AlertTriangle className="w-3.5 h-3.5" />
            Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-surface text-text-muted border border-border">
            <X className="w-3.5 h-3.5" />
            Cancelled
          </span>
        );
      case "queued":
      default:
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-surface text-text-muted border border-border">
            <Clock className="w-3.5 h-3.5" />
            Queued
          </span>
        );
    }
  };

  return (
    <motion.div
      ref={ref}
      {...cardHover}
      layout
      data-testid={`task-card-${task.id}`}
      className="p-4 sm:p-5 rounded-xl bg-bg-elevated border border-border hover:border-border/80 transition-colors shadow-1 flex flex-col gap-4"
    >
      {/* Header: Icon, Name, and Status Badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-surface border border-border flex items-center justify-center flex-shrink-0 text-text-muted">
            {isMagnet ? (
              <Magnet className="w-4 h-4 text-accent-1" />
            ) : (
              <LinkIcon className="w-4 h-4 text-accent-2" />
            )}
          </div>
          <div className="min-w-0">
            <h3
              className="font-medium text-sm sm:text-base text-text truncate tracking-tight"
              title={task.name}
            >
              {task.name}
            </h3>
            <p className="text-xs text-text-muted font-mono truncate" title={task.source_uri}>
              {isMagnet && task.info_hash
                ? `hash: ${task.info_hash.slice(0, 16)}...`
                : task.source_uri}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {renderBadge()}

          {task.state === "awaiting_selection" && onSelectFiles && (
            <button
              type="button"
              onClick={() => onSelectFiles(task)}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-accent-grad text-white text-xs font-semibold shadow-glow hover:opacity-95 transition-opacity"
            >
              <FolderDown className="w-3.5 h-3.5" />
              <span>Select Files</span>
            </button>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-1 ml-1">
            {canPause && (
              <button
                type="button"
                onClick={() => handleAction(() => onPause!(task.id))}
                disabled={isActing}
                className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-text transition-colors"
                title="Pause task"
                aria-label="Pause task"
              >
                {isActing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Pause className="w-4 h-4" />
                )}
              </button>
            )}

            {canResume && (
              <button
                type="button"
                onClick={() => handleAction(() => onResume!(task.id))}
                disabled={isActing}
                className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-text transition-colors"
                title="Resume task"
                aria-label="Resume task"
              >
                {isActing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
              </button>
            )}

            {canCancel && (
              <button
                type="button"
                onClick={() => handleAction(() => onCancel!(task.id))}
                disabled={isActing}
                className="p-1.5 rounded-md hover:bg-danger/10 text-text-muted hover:text-danger transition-colors"
                title="Cancel task"
                aria-label="Cancel task"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {task.state === "failed" && onRetry && (
              <button
                type="button"
                onClick={() => handleAction(() => onRetry!(task.id))}
                disabled={isActing}
                className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-accent-1 transition-colors"
                title="Retry task"
                aria-label="Retry task"
              >
                {isActing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RotateCcw className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress Bar & Numerical stats */}
      <ProgressBar
        progress={task.progress}
        state={task.state}
        speedBps={task.speed_bps}
        downloadedBytes={task.downloaded_bytes}
        totalBytes={task.total_bytes || task.size_bytes || 0}
        etaSeconds={task.eta_seconds}
      />

      {/* Failure Error Display with Retry Action */}
      {task.state === "failed" && (
        <div
          data-testid="task-error-banner"
          className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-xs text-danger flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span className="truncate">{task.error || "Download task failed"}</span>
          </div>
          {onRetry && (
            <button
              type="button"
              onClick={() => handleAction(() => onRetry!(task.id))}
              disabled={isActing}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-danger/20 hover:bg-danger/30 text-danger font-medium transition-colors flex-shrink-0"
              title="Retry failed task"
              aria-label="Retry task button"
            >
              {isActing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCcw className="w-3.5 h-3.5" />
              )}
              <span>Retry</span>
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
});

TaskCard.displayName = "TaskCard";
