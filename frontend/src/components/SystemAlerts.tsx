import React, { useEffect, useState } from "react";
import {
  WifiOff,
  AlertTriangle,
  HardDrive,
  Unlink,
  ExternalLink,
  RotateCcw,
  X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/hooks/useAuth";
import { useStorage } from "@/hooks/useStorage";
import { formatBytes } from "@/lib/format";

export const SystemAlerts: React.FC = () => {
  const { user, login } = useAuth();
  const { storage, error: storageError, refetch: refetchStorage } = useStorage(!!user);

  const [isOnline, setIsOnline] = useState<boolean>(() => {
    return typeof navigator !== "undefined" ? navigator.onLine : true;
  });
  const [dismissedAlmostFull, setDismissedAlmostFull] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const isDriveDisconnected =
    !!user &&
    !!storageError &&
    (storageError.toLowerCase().includes("disconnect") ||
      storageError.toLowerCase().includes("token") ||
      storageError.toLowerCase().includes("auth"));

  const isDriveFull =
    !!user && !!storage && (storage.free_bytes <= 0 || storage.percent_used >= 100);

  const isDriveAlmostFull =
    !!user &&
    !!storage &&
    storage.percent_used >= 90 &&
    storage.percent_used < 100 &&
    !dismissedAlmostFull;

  return (
    <div className="w-full flex flex-col gap-2.5 px-4 sm:px-8 max-w-7xl mx-auto pt-2" data-testid="system-alerts-container">
      <AnimatePresence>
        {/* 1. Offline Alert */}
        {!isOnline && (
          <motion.div
            key="offline-alert"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            data-testid="offline-alert"
            className="w-full p-3 rounded-xl bg-danger/15 border border-danger/30 text-danger text-xs flex items-center justify-between gap-3 shadow-1"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <WifiOff className="w-4 h-4 flex-shrink-0 animate-pulse" />
              <div>
                <span className="font-semibold mr-1.5">You are currently offline:</span>
                <span className="text-danger/90">
                  Internet connection lost. Downloads and live progress updates will resume when
                  reconnected.
                </span>
              </div>
            </div>
          </motion.div>
        )}

        {/* 2. Drive Disconnected Alert */}
        {isDriveDisconnected && (
          <motion.div
            key="drive-disconnected-alert"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            data-testid="drive-disconnected-alert"
            className="w-full p-3 rounded-xl bg-warning/15 border border-warning/40 text-warning text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-1"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <Unlink className="w-4 h-4 flex-shrink-0" />
              <div>
                <span className="font-semibold mr-1.5">Google Drive Disconnected:</span>
                <span className="text-warning/90">
                  Your Drive authorization has expired or was revoked. Reconnect your account to save files.
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
              <button
                type="button"
                onClick={() => refetchStorage()}
                className="p-1.5 rounded-lg hover:bg-warning/20 transition-colors"
                title="Retry connecting"
                aria-label="Retry storage connection"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={login}
                className="px-3 py-1.5 rounded-lg bg-warning text-black font-semibold hover:bg-warning/90 transition-colors text-xs"
              >
                Reconnect Drive
              </button>
            </div>
          </motion.div>
        )}

        {/* 3. Drive Full Alert */}
        {isDriveFull && (
          <motion.div
            key="drive-full-alert"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            data-testid="drive-full-alert"
            className="w-full p-3.5 rounded-xl bg-danger/20 border border-danger/40 text-danger text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-1"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <HardDrive className="w-4 h-4 flex-shrink-0" />
              <div>
                <span className="font-semibold mr-1.5">Google Drive Storage Full (0 B Free):</span>
                <span className="text-danger/90">
                  Drive quota is completely exhausted. No downloads can be saved until space is cleared.
                </span>
              </div>
            </div>

            <a
              href="https://drive.google.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-danger text-white font-semibold hover:bg-danger/90 transition-colors text-xs self-end sm:self-auto flex-shrink-0"
            >
              <span>Manage Drive</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </motion.div>
        )}

        {/* 4. Drive Almost Full Warning */}
        {isDriveAlmostFull && (
          <motion.div
            key="drive-almost-full-alert"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            data-testid="drive-almost-full-alert"
            className="w-full p-3 rounded-xl bg-warning/10 border border-warning/30 text-warning text-xs flex items-center justify-between gap-3 shadow-1"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <div>
                <span className="font-semibold mr-1.5">
                  Drive Storage Almost Full ({storage?.percent_used}%):
                </span>
                <span className="text-warning/90">
                  Only {formatBytes(storage?.free_bytes)} free space remaining. Free up space to prevent downloads from pausing.
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setDismissedAlmostFull(true)}
              className="p-1 rounded-md hover:bg-warning/20 transition-colors flex-shrink-0"
              title="Dismiss warning"
              aria-label="Dismiss warning"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
