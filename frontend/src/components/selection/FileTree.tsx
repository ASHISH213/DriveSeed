import React, { useMemo, useState } from "react";
import { CheckSquare, Square, Search, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { TaskFile } from "@/types/task";
import { formatBytes } from "@/lib/format";
import { getFileCategory, renderFileIcon } from "@/lib/fileIcons";

interface FileTreeProps {
  files: TaskFile[];
  selectedIds: Set<string>;
  onToggleFile: (fileId: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

export const FileTree: React.FC<FileTreeProps> = ({
  files,
  selectedIds,
  onToggleFile,
  onSelectAll,
  onDeselectAll,
}) => {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredFiles = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => f.path.toLowerCase().includes(q));
  }, [files, searchQuery]);

  const allSelected = files.length > 0 && selectedIds.size === files.length;
  const noneSelected = selectedIds.size === 0;

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Top Bar: Search and Selection Controls */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter files in download..."
            className="w-full pl-9 pr-8 py-1.5 text-xs rounded-lg bg-surface border border-border text-text placeholder-text-muted focus:outline-none focus:border-accent-1/50 transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text transition-colors"
              title="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Quick select buttons */}
        <div className="flex items-center gap-1.5 flex-shrink-0 self-end sm:self-auto text-xs">
          <button
            type="button"
            onClick={onSelectAll}
            disabled={allSelected}
            className="px-2.5 py-1 rounded-md bg-surface border border-border text-text hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Select All
          </button>
          <button
            type="button"
            onClick={onDeselectAll}
            disabled={noneSelected}
            className="px-2.5 py-1 rounded-md bg-surface border border-border text-text hover:bg-surface-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Deselect All
          </button>
        </div>
      </div>

      {/* File List */}
      <div className="max-h-64 sm:max-h-72 overflow-y-auto rounded-lg border border-border bg-bg/50 divide-y divide-border/40 scrollbar-thin">
        {filteredFiles.length === 0 ? (
          <div className="p-8 text-center text-xs text-text-muted">
            {files.length === 0 ? "No files detected in task" : "No files match your search filter"}
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {filteredFiles.map((file) => {
              const isSelected = selectedIds.has(file.id);
              const category = getFileCategory(file.path, "");
              const pathParts = file.path.split("/");
              const fileName = pathParts.pop() || file.path;
              const dirPath = pathParts.join("/");

              return (
                <motion.div
                  key={file.id}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => onToggleFile(file.id)}
                  className={`group flex items-center justify-between gap-3 px-3.5 py-2.5 cursor-pointer text-xs transition-colors ${
                    isSelected
                      ? "bg-accent-1/5 hover:bg-accent-1/10"
                      : "opacity-60 hover:opacity-100 hover:bg-surface/50"
                  }`}
                  data-testid={`file-row-${file.id}`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <button
                      type="button"
                      aria-label={`Select ${fileName}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleFile(file.id);
                      }}
                      className="text-text-muted hover:text-accent-1 transition-colors flex-shrink-0"
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-accent-1" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>

                    <div className="flex-shrink-0">
                      {renderFileIcon(category, "w-4 h-4")}
                    </div>

                    <div className="min-w-0 flex flex-col">
                      <span className="text-text font-medium truncate" title={file.path}>
                        {fileName}
                      </span>
                      {dirPath && (
                        <span className="text-[10px] text-text-muted truncate font-mono" title={dirPath}>
                          {dirPath}
                        </span>
                      )}
                    </div>
                  </div>

                  <span className="text-text-muted font-mono flex-shrink-0 text-[11px]">
                    {formatBytes(file.size_bytes)}
                  </span>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
};
