import React from "react";
import { Search, FolderPlus, LayoutGrid, List, RefreshCw, X } from "lucide-react";
import type { ViewMode } from "@/types/library";

interface LibraryToolbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onNewFolder: () => void;
  onRefresh: () => void;
  isLoading?: boolean;
}

export const LibraryToolbar: React.FC<LibraryToolbarProps> = ({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onNewFolder,
  onRefresh,
  isLoading = false,
}) => {
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl bg-bg-elevated border border-border shadow-1">
      {/* Search Bar */}
      <div className="relative flex-1 max-w-md">
        <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 transform -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search library files by name..."
          className="w-full pl-9 pr-8 py-1.5 text-xs sm:text-sm rounded-lg bg-surface border border-border text-text placeholder-text-muted focus:outline-none focus:border-accent-1 transition-colors"
          aria-label="Search files"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-2.5 top-1/2 transform -translate-y-1/2 p-0.5 rounded hover:bg-surface text-text-muted hover:text-text"
            title="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Action Buttons: New Folder, Refresh, View Mode Switcher */}
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <button
          type="button"
          onClick={onNewFolder}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border hover:bg-surface-hover text-text text-xs font-medium transition-colors"
          title="Create a new folder"
        >
          <FolderPlus className="w-4 h-4 text-accent-1" />
          <span>New Folder</span>
        </button>

        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="p-2 rounded-lg bg-surface border border-border hover:bg-surface-hover text-text-muted hover:text-text transition-colors disabled:opacity-50"
          title="Refresh library"
          aria-label="Refresh library"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
        </button>

        {/* View Mode Toggle */}
        <div className="flex items-center p-0.5 rounded-lg bg-surface border border-border">
          <button
            type="button"
            onClick={() => onViewModeChange("grid")}
            className={`p-1.5 rounded-md transition-all ${
              viewMode === "grid"
                ? "bg-bg text-text shadow-1"
                : "text-text-muted hover:text-text"
            }`}
            title="Grid view"
            aria-label="Grid view"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => onViewModeChange("list")}
            className={`p-1.5 rounded-md transition-all ${
              viewMode === "list"
                ? "bg-bg text-text shadow-1"
                : "text-text-muted hover:text-text"
            }`}
            title="List view"
            aria-label="List view"
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
