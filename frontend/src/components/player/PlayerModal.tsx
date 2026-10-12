import React from "react";
import { motion } from "framer-motion";
import type { LibraryItem } from "@/types/library";
import { PlayerShell } from "./PlayerShell";

interface PlayerModalProps {
  file: LibraryItem | null;
  onClose: () => void;
}

export const PlayerModal: React.FC<PlayerModalProps> = ({ file, onClose }) => {
  if (!file) return null;

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
        <PlayerShell
          fileId={file.id}
          fileName={file.name}
          mimeType={file.mime_type}
          onClose={onClose}
        />
      </motion.div>
    </div>
  );
};
