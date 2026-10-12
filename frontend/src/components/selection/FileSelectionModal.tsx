import React, { useEffect, useMemo, useState } from "react";
import {
  X,
  HardDrive,
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  FolderDown,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { Task, TaskStartRequest } from "@/types/task";
import { FileTree } from "./FileTree";
import { FolderPicker } from "./FolderPicker";
import { useStorage } from "@/hooks/useStorage";
import { formatBytes } from "@/lib/format";
import { useMotionPreset } from "@/lib/motion";

interface FileSelectionModalProps {
  isOpen: boolean;
  task: Task | null;
  onClose: () => void;
  onStart: (taskId: string, req: TaskStartRequest) => Promise<void>;
}

export const FileSelectionModal: React.FC<FileSelectionModalProps> = ({
  isOpen,
  task,
  onClose,
  onStart,
}) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    if (task?.files) {
      for (const file of task.files) {
        if (file.selected !== false) {
          initial.add(file.id);
        }
      }
    }
    return initial;
  });
  const [destinationFolderId, setDestinationFolderId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { storage } = useStorage(isOpen);
  const { modal } = useMotionPreset();

  // Reset or re-initialize selected IDs when a different task opens
  useEffect(() => {
    if (task && task.files && isOpen) {
      const next = new Set<string>();
      for (const file of task.files) {
        if (file.selected !== false) {
          next.add(file.id);
        }
      }
      setSelectedIds(next);
      setDestinationFolderId(null);
      setError(null);
    }
  }, [task, isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  // Compute selected total size
  const totalSelectedBytes = useMemo(() => {
    if (!task?.files) return 0;
    return task.files
      .filter((f) => selectedIds.has(f.id))
      .reduce((sum, f) => sum + (f.size_bytes || 0), 0);
  }, [task, selectedIds]);

  // Space check calculation
  const hasStorageData = !!storage;
  const isInsufficientSpace =
    hasStorageData && totalSelectedBytes > (storage?.free_bytes ?? 0);

  const handleToggleFile = (fileId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (!task?.files) return;
    setSelectedIds(new Set(task.files.map((f) => f.id)));
  };

  const handleDeselectAll = () => {
    setSelectedIds(new Set());
  };

  const handleConfirmStart = async () => {
    if (!task || isSubmitting || isInsufficientSpace) return;
    if (selectedIds.size === 0) {
      setError("Please select at least one file to download.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onStart(task.id, {
        selected_file_ids: Array.from(selectedIds),
        destination_folder_id: destinationFolderId,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start download task");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen || !task) return null;

  const totalFiles = task.files?.length || 0;
  const selectedCount = selectedIds.size;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => {
            if (!isSubmitting) onClose();
          }}
          className="fixed inset-0 bg-black/75 backdrop-blur-sm"
          aria-hidden="true"
        />

        {/* Modal Window */}
        <motion.div
          {...modal}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className="relative w-full max-w-2xl bg-bg-elevated border border-border rounded-2xl shadow-2 overflow-hidden flex flex-col z-10 my-auto"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 sm:p-5 border-b border-border">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-accent-1/10 border border-accent-1/30 flex items-center justify-center text-accent-1 flex-shrink-0">
                <FolderDown className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <h2 id="modal-title" className="text-base sm:text-lg font-semibold text-text truncate">
                  Select Files to Download
                </h2>
                <p className="text-xs text-text-muted truncate font-mono" title={task.name}>
                  {task.name}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="p-1.5 rounded-lg text-text-muted hover:text-text hover:bg-surface transition-colors disabled:opacity-40"
              title="Close modal"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Modal Body */}
          <div className="p-4 sm:p-6 flex flex-col gap-5 overflow-y-auto max-h-[calc(85vh-130px)]">
            {/* Storage Quota / Free Space Meter Banner */}
            <div
              className={`p-3 sm:p-3.5 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs ${
                isInsufficientSpace
                  ? "bg-danger/10 border-danger/30 text-danger"
                  : "bg-surface border-border text-text"
              }`}
            >
              <div className="flex items-center gap-2.5">
                {isInsufficientSpace ? (
                  <AlertTriangle className="w-4 h-4 text-danger flex-shrink-0" />
                ) : (
                  <HardDrive className="w-4 h-4 text-accent-1 flex-shrink-0" />
                )}
                <div>
                  <div className="font-medium">
                    {isInsufficientSpace
                      ? "Insufficient Google Drive Storage"
                      : "Google Drive Storage Space"}
                  </div>
                  <div className="text-[11px] text-text-muted mt-0.5">
                    {hasStorageData ? (
                      <>
                        Free Space:{" "}
                        <span className="font-mono text-text font-medium">
                          {formatBytes(storage?.free_bytes)}
                        </span>{" "}
                        / Total:{" "}
                        <span className="font-mono">{formatBytes(storage?.total_bytes)}</span>
                      </>
                    ) : (
                      "Checking Drive free space..."
                    )}
                  </div>
                </div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-1.5 self-end sm:self-auto flex-shrink-0">
                {isInsufficientSpace ? (
                  <span className="px-2.5 py-1 rounded-full bg-danger/20 text-danger font-semibold text-[11px] border border-danger/40">
                    Need {formatBytes(totalSelectedBytes - (storage?.free_bytes ?? 0))} more
                  </span>
                ) : (
                  <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-success/15 text-success font-medium text-[11px] border border-success/30">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Space Verified
                  </span>
                )}
              </div>
            </div>

            {/* Destination Folder Picker */}
            <FolderPicker
              selectedFolderId={destinationFolderId}
              onSelectFolder={(folderId) => setDestinationFolderId(folderId)}
            />

            {/* File Tree */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-xs px-0.5">
                <span className="font-medium text-text">Choose Files</span>
                <span data-testid="selected-summary" className="text-text-muted font-mono">
                  {selectedCount} of {totalFiles} files selected ({formatBytes(totalSelectedBytes)})
                </span>
              </div>

              <FileTree
                files={task.files || []}
                selectedIds={selectedIds}
                onToggleFile={handleToggleFile}
                onSelectAll={handleSelectAll}
                onDeselectAll={handleDeselectAll}
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Footer Controls */}
          <div className="p-4 sm:p-5 border-t border-border bg-bg/40 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="text-xs text-text-muted flex items-center gap-1.5 font-mono">
              <span>Total Selected:</span>
              <span className="text-text font-semibold">{formatBytes(totalSelectedBytes)}</span>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="flex-1 sm:flex-initial px-4 py-2 rounded-xl bg-surface border border-border text-text hover:bg-surface-hover text-xs font-medium transition-colors disabled:opacity-40"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleConfirmStart}
                disabled={isSubmitting || isInsufficientSpace || selectedCount === 0}
                className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-5 py-2 rounded-xl bg-accent-grad text-white text-xs font-semibold shadow-glow hover:opacity-95 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                title={
                  isInsufficientSpace
                    ? "Cannot start: free space exceeded"
                    : selectedCount === 0
                    ? "Select at least one file"
                    : "Start download to Drive"
                }
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Starting...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Start Download</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
