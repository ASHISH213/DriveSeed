import React, { useState } from "react";
import { MoreVertical, Edit3, FolderInput, Trash2 } from "lucide-react";
import { motion } from "framer-motion";
import type { LibraryItem } from "@/types/library";
import { formatBytes } from "@/lib/format";
import { getFileCategory, renderFileIcon } from "@/lib/fileIcons";
import { useMotionPreset } from "@/lib/motion";

interface FileItemCardProps {
  item: LibraryItem;
  onOpen: (item: LibraryItem) => void;
  onRename: (item: LibraryItem) => void;
  onMove: (item: LibraryItem) => void;
  onDelete: (item: LibraryItem) => void;
}

export const FileItemCard = React.forwardRef<HTMLDivElement, FileItemCardProps>(
  ({ item, onOpen, onRename, onMove, onDelete }, ref) => {
    const [showMenu, setShowMenu] = useState(false);
    const { cardHover } = useMotionPreset();
    const category = getFileCategory(item.name, item.mime_type);

    return (
      <motion.div
        ref={ref}
        {...cardHover}
        layout
        data-testid={`file-card-${item.id}`}
        className="group relative flex flex-col justify-between p-4 rounded-xl bg-bg-elevated border border-border hover:border-accent-1/50 transition-all shadow-1 cursor-pointer select-none"
        onClick={() => onOpen(item)}
      >
        {/* Top Bar: Icon + Action Menu */}
        <div className="flex items-start justify-between gap-2">
          <div className="w-10 h-10 rounded-lg bg-surface border border-border flex items-center justify-center flex-shrink-0">
            {renderFileIcon(category, "w-5 h-5")}
          </div>

          {/* Action Menu */}
          <div
            className="relative"
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <button
              type="button"
              onClick={() => setShowMenu((prev) => !prev)}
              className="p-1 rounded-md hover:bg-surface text-text-muted hover:text-text transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
              title="File actions"
              aria-label="File actions"
            >
              <MoreVertical className="w-4 h-4" />
            </button>

          {showMenu && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowMenu(false)}
              />
              <div className="absolute right-0 top-6 z-50 w-36 rounded-lg bg-bg-elevated border border-border p-1 shadow-2 flex flex-col text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setShowMenu(false);
                    onRename(item);
                  }}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded hover:bg-surface text-text text-left"
                >
                  <Edit3 className="w-3.5 h-3.5 text-accent-1" />
                  <span>Rename</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowMenu(false);
                    onMove(item);
                  }}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded hover:bg-surface text-text text-left"
                >
                  <FolderInput className="w-3.5 h-3.5 text-accent-2" />
                  <span>Move</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowMenu(false);
                    onDelete(item);
                  }}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded hover:bg-danger/10 text-danger text-left"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Delete</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Info: Name and Size */}
      <div className="mt-4 flex flex-col gap-1 min-w-0">
        <h4
          className="font-medium text-xs sm:text-sm text-text truncate group-hover:text-accent-1 transition-colors"
          title={item.name}
        >
          {item.name}
        </h4>
        <span className="text-[11px] font-mono tabular-nums text-text-muted">
          {item.is_folder ? "Folder" : formatBytes(item.size_bytes)}
        </span>
      </div>
    </motion.div>
    );
  }
);

FileItemCard.displayName = "FileItemCard";

