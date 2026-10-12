import React, { useState } from "react";
import { HardDrive, AlertTriangle, CloudOff } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { formatBytes } from "@/lib/format";
import { useStorage } from "@/hooks/useStorage";
import type { StorageQuota } from "@/types/storage";

export interface StorageRingProps {
  storage?: StorageQuota | null;
  isLoading?: boolean;
  error?: string | null;
  isLoggedIn?: boolean;
}

export const StorageRing: React.FC<StorageRingProps> = ({
  storage: propStorage,
  isLoading: propLoading,
  error: propError,
  isLoggedIn = true,
}) => {
  const [showPopover, setShowPopover] = useState(false);

  // Use hook if props are not explicitly provided
  const hookResult = useStorage(isLoggedIn && propStorage === undefined);
  const storage = propStorage !== undefined ? propStorage : hookResult.storage;
  const isLoading = propLoading !== undefined ? propLoading : hookResult.isLoading;
  const error = propError !== undefined ? propError : hookResult.error;

  const percentUsed = storage ? Math.min(100, Math.max(0, storage.percent_used)) : 0;

  // Determine status color class based on percent
  let statusColorClass = "text-success";
  let statusBgClass = "bg-success";
  if (percentUsed >= 90) {
    statusColorClass = "text-danger";
    statusBgClass = "bg-danger";
  } else if (percentUsed >= 75) {
    statusColorClass = "text-warning";
    statusBgClass = "bg-warning";
  }

  // Label text
  let labelText = "Drive Ready";
  if (isLoading) {
    labelText = "Connecting...";
  } else if (storage) {
    labelText = `${formatBytes(storage.used_bytes)} / ${formatBytes(storage.total_bytes)}`;
  } else if (error) {
    labelText = "Drive Disconnected";
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowPopover(true)}
      onMouseLeave={() => setShowPopover(false)}
    >
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface border border-border hover:bg-surface-hover transition-colors cursor-pointer select-none"
        title={storage ? `Storage: ${storage.percent_used}% used` : labelText}
        data-testid="storage-indicator"
      >
        {/* Radial Progress Ring */}
        <div
          className="relative w-5 h-5 flex items-center justify-center flex-shrink-0"
          data-testid="storage-ring"
        >
          <svg className="w-5 h-5 transform -rotate-90" viewBox="0 0 36 36">
            {/* Background Circle */}
            <path
              className="text-border"
              strokeWidth="4"
              stroke="currentColor"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            {/* Animated Progress Circle */}
            {storage && (
              <path
                className={`${statusColorClass} transition-all duration-500 ease-out`}
                strokeDasharray={`${percentUsed}, 100`}
                strokeWidth="4"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            )}
          </svg>

          {/* Center Icon */}
          {error ? (
            <CloudOff className="w-2.5 h-2.5 text-danger absolute" />
          ) : percentUsed >= 90 ? (
            <AlertTriangle className="w-2.5 h-2.5 text-danger absolute" />
          ) : (
            <HardDrive className="w-2.5 h-2.5 text-text-muted absolute" />
          )}
        </div>

        {/* Text Label */}
        <span
          className="text-xs font-mono tabular-nums text-text-muted hidden sm:inline"
          data-testid="storage-label"
        >
          {labelText}
        </span>
      </div>

      {/* Hover Breakdown Popover */}
      <AnimatePresence>
        {showPopover && storage && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-64 p-3 rounded-xl bg-bg-elevated/95 backdrop-blur-xl border border-border shadow-2 flex flex-col gap-2.5 z-50 text-xs"
            data-testid="storage-popover"
          >
            <div className="flex items-center justify-between pb-1.5 border-b border-border">
              <span className="font-semibold text-text">Google Drive Storage</span>
              <span className={`font-mono font-semibold ${statusColorClass}`}>
                {storage.percent_used}%
              </span>
            </div>

            {/* Visual Progress Bar */}
            <div className="w-full h-2 rounded-full bg-surface overflow-hidden relative">
              <div
                className={`h-full ${statusBgClass} transition-all duration-300`}
                style={{ width: `${percentUsed}%` }}
              />
            </div>

            {/* Metrics Breakdown */}
            <div className="flex flex-col gap-1 font-mono text-[11px] text-text-muted">
              <div className="flex justify-between">
                <span>Used:</span>
                <span className="text-text font-medium">
                  {formatBytes(storage.used_bytes)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Free Space:</span>
                <span className="text-text font-medium">
                  {formatBytes(storage.free_bytes)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Total Capacity:</span>
                <span className="text-text font-medium">
                  {formatBytes(storage.total_bytes)}
                </span>
              </div>
            </div>

            {/* Near Capacity Warning */}
            {percentUsed >= 90 && (
              <div className="flex items-center gap-1.5 p-2 rounded-md bg-danger/10 border border-danger/20 text-danger text-[10px]">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Drive is nearly full. Clean up space or upgrade Drive.</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
