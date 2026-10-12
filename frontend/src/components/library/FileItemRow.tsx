import React from "react";
import { Edit3, FolderInput, Trash2, Play } from "lucide-react";
import { motion } from "framer-motion";
import type { LibraryItem } from "@/types/library";
import { formatBytes } from "@/lib/format";
import { getFileCategory, renderFileIcon } from "@/lib/fileIcons";
import { useMotionPreset, spring } from "@/lib/motion";

interface FileItemRowProps {
  item: LibraryItem;
  onOpen: (item: LibraryItem) => void;
  onRename: (item: LibraryItem) => void;
  onMove: (item: LibraryItem) => void;
  onDelete: (item: LibraryItem) => void;
}

export const FileItemRow = React.forwardRef<HTMLDivElement, FileItemRowProps>(
  ({ item, onOpen, onRename, onMove, onDelete }, ref) => {
    const category = getFileCategory(item.name, item.mime_type);
    const { cardHover } = useMotionPreset();

    return (
      <motion.div
        ref={ref}
        {...cardHover}
        layout
        layoutId={`library-item-${item.id}`}
        transition={spring.soft}
        data-testid={`file-row-${item.id}`}
        onClick={() => onOpen(item)}
        className="group flex items-center justify-between p-3 rounded-lg bg-bg-elevated border border-border hover:border-accent-1/40 hover:bg-surface/50 transition-colors cursor-pointer select-none"
      >
        {/* Left: Icon & Name */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="w-8 h-8 rounded-md bg-surface border border-border flex items-center justify-center flex-shrink-0">
            {renderFileIcon(category, "w-4 h-4")}
          </div>
          <div className="min-w-0 flex-1">
            <p
              className="font-medium text-xs sm:text-sm text-text truncate group-hover:text-accent-1 transition-colors"
              title={item.name}
            >
              {item.name}
            </p>
            <p className="text-[11px] text-text-muted font-mono truncate hidden sm:block">
              {item.mime_type}
            </p>
          </div>
        </div>

        {/* Right: Size + Action Buttons */}
        <div className="flex items-center gap-4 flex-shrink-0 ml-4">
          <span className="text-xs font-mono tabular-nums text-text-muted w-20 text-right">
            {item.is_folder ? "Folder" : formatBytes(item.size_bytes)}
          </span>

          <div
            className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            {(category === "video" || category === "audio") && (
              <button
                type="button"
                onClick={() => onOpen(item)}
                className="p-1.5 rounded-md hover:bg-surface text-accent-1 hover:text-accent-1 transition-colors"
                title="Play media"
                aria-label="Play media"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
              </button>
            )}
            <button
              type="button"
              onClick={() => onRename(item)}
              className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-text transition-colors"
              title="Rename"
              aria-label="Rename"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onMove(item)}
              className="p-1.5 rounded-md hover:bg-surface text-text-muted hover:text-text transition-colors"
              title="Move"
              aria-label="Move"
            >
              <FolderInput className="w-3.5 h-3.5 text-accent-2" />
            </button>
            <button
              type="button"
              onClick={() => onDelete(item)}
              className="p-1.5 rounded-md hover:bg-danger/10 text-text-muted hover:text-danger transition-colors"
              title="Delete"
              aria-label="Delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </motion.div>
    );
  }
);

FileItemRow.displayName = "FileItemRow";
