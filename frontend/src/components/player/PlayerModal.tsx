import React from "react";
import { motion } from "framer-motion";
import { ExternalLink, X, HardDrive } from "lucide-react";
import type { LibraryItem } from "@/types/library";
import type { Task } from "@/types/task";
import { useCapabilities } from "@/hooks/useCapabilities";
import { PlayerShell } from "./PlayerShell";

interface PlayerModalProps {
  file?: LibraryItem | null;
  task?: Task | null;
  onClose: () => void;
}

export const PlayerModal: React.FC<PlayerModalProps> = ({ file, task, onClose }) => {
  const { capabilities } = useCapabilities();
  const isStreamingEnabled = capabilities?.features?.streaming ?? true;

  if (!file && !task) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md"
      data-testid="player-modal"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full h-full sm:max-w-6xl sm:h-[85vh] sm:rounded-2xl overflow-hidden bg-black border border-white/10 shadow-2"
      >
        {!isStreamingEnabled ? (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center bg-bg-surface">
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-full bg-surface/50 hover:bg-surface text-text-muted hover:text-text transition-colors"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="w-16 h-16 rounded-2xl bg-accent-1/10 border border-accent-1/20 flex items-center justify-center text-accent-1 mb-4">
              <HardDrive className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-semibold text-text mb-2">Google Drive Native Playback</h2>
            <p className="text-sm text-text-muted max-w-md mb-6">
              In Google Colab mode, media proxying is disabled to comply with Colab usage rules.
              You can play or view &ldquo;{file?.name || task?.name}&rdquo; directly in Google Drive.
            </p>
            {file && (
              <a
                href={`/api/stream/${file.id}/handoff`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent-grad text-white font-medium shadow-1 hover:opacity-95 transition-opacity"
              >
                <span>Open in Google Drive</span>
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
        ) : file ? (
          <PlayerShell
            fileId={file.id}
            fileName={file.name}
            mimeType={file.mime_type}
            onClose={onClose}
          />
        ) : task ? (
          <PlayerShell
            taskId={task.id}
            fileName={task.name}
            onClose={onClose}
          />
        ) : null}
      </motion.div>
    </div>
  );
};
