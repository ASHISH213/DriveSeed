import React, { useState } from "react";
import { Folder, SearchX, AlertCircle, LogIn } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import type { LibraryItem } from "@/types/library";
import { useLibrary } from "@/hooks/useLibrary";
import { useAuth } from "@/hooks/useAuth";
import { Breadcrumbs } from "@/components/library/Breadcrumbs";
import { LibraryToolbar } from "@/components/library/LibraryToolbar";
import { FileItemCard } from "@/components/library/FileItemCard";
import { FileItemRow } from "@/components/library/FileItemRow";
import {
  CreateFolderModal,
  RenameModal,
  MoveModal,
  DeleteConfirmModal,
} from "@/components/library/LibraryModals";
import { PlayerModal } from "@/components/player/PlayerModal";
import { isMediaFile } from "@/lib/fileIcons";
import { useMotionPreset } from "@/lib/motion";

export const Library: React.FC = () => {
  const { user, isLoading: isAuthLoading, login } = useAuth();
  const {
    files,
    breadcrumbs,
    currentFolderId,
    searchQuery,
    setSearchQuery,
    viewMode,
    setViewMode,
    isLoading: isFilesLoading,
    error,
    refreshLibrary,
    navigateToFolder,
    createFolder,
    renameItem,
    moveItem,
    deleteItem,
  } = useLibrary(!!user);

  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [activeRenameItem, setActiveRenameItem] = useState<LibraryItem | null>(null);
  const [activeMoveItem, setActiveMoveItem] = useState<LibraryItem | null>(null);
  const [activeDeleteItem, setActiveDeleteItem] = useState<LibraryItem | null>(null);
  const [activePlayFile, setActivePlayFile] = useState<LibraryItem | null>(null);

  const { slideFade } = useMotionPreset();

  const handleOpenItem = (item: LibraryItem) => {
    if (item.is_folder) {
      navigateToFolder(item.id, item.name);
    } else if (isMediaFile(item.name, item.mime_type)) {
      setActivePlayFile(item);
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 flex flex-col gap-6">
      {/* Unauthenticated notice */}
      {!isAuthLoading && !user && (
        <motion.div
          {...slideFade}
          className="w-full max-w-xl mx-auto p-6 rounded-xl bg-surface border border-border text-center flex flex-col items-center gap-3 shadow-1"
        >
          <div className="w-10 h-10 rounded-full bg-accent-1/10 flex items-center justify-center text-accent-1">
            <LogIn className="w-5 h-5" />
          </div>
          <h2 className="text-base font-semibold text-text">Sign In with Google to Browse Library</h2>
          <p className="text-xs text-text-muted max-w-sm">
            DriveSeed manages files directly in your Google Drive. Sign in to browse your seedbox files.
          </p>
          <button
            type="button"
            onClick={login}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-grad text-white text-xs font-semibold shadow-glow hover:opacity-95 transition-opacity"
          >
            Sign In with Google
          </button>
        </motion.div>
      )}

      {user && (
        <>
          {/* Breadcrumbs Navigation */}
          <Breadcrumbs
            items={breadcrumbs}
            onNavigate={(id, name) => navigateToFolder(id, name)}
          />

          {/* Library Toolbar */}
          <LibraryToolbar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onNewFolder={() => setShowCreateFolder(true)}
            onRefresh={refreshLibrary}
            isLoading={isFilesLoading}
          />

          {/* Error Banner */}
          {error && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={refreshLibrary}
                className="underline hover:opacity-80"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading Skeletons */}
          {isFilesLoading && files.length === 0 && (
            <div
              className={
                viewMode === "grid"
                  ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
                  : "flex flex-col gap-2"
              }
            >
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div
                  key={i}
                  className={`rounded-xl bg-surface/50 border border-border animate-pulse ${
                    viewMode === "grid" ? "h-32" : "h-14"
                  }`}
                />
              ))}
            </div>
          )}

          {/* Empty Folder State */}
          {!isFilesLoading && files.length === 0 && !searchQuery && (
            <motion.div
              {...slideFade}
              className="flex flex-col items-center justify-center p-12 text-center rounded-xl bg-surface/30 border border-dashed border-border"
            >
              <div className="w-12 h-12 rounded-xl bg-surface border border-border flex items-center justify-center mb-3 text-text-muted">
                <Folder className="w-6 h-6 text-accent-1 opacity-70" />
              </div>
              <h3 className="font-medium text-sm sm:text-base text-text mb-1">
                This folder is empty
              </h3>
              <p className="text-xs text-text-muted max-w-sm mb-4">
                Completed downloads will appear here automatically. You can also create subfolders to organize your files.
              </p>
              <button
                type="button"
                onClick={() => setShowCreateFolder(true)}
                className="px-3.5 py-1.5 rounded-lg bg-surface border border-border hover:bg-surface-hover text-xs font-medium text-text transition-colors"
              >
                Create a subfolder
              </button>
            </motion.div>
          )}

          {/* Empty Search State */}
          {!isFilesLoading && files.length === 0 && searchQuery && (
            <motion.div
              {...slideFade}
              className="flex flex-col items-center justify-center p-12 text-center rounded-xl bg-surface/30 border border-dashed border-border"
            >
              <div className="w-12 h-12 rounded-xl bg-surface border border-border flex items-center justify-center mb-3 text-text-muted">
                <SearchX className="w-6 h-6 text-warning opacity-70" />
              </div>
              <h3 className="font-medium text-sm sm:text-base text-text mb-1">
                No files matching &quot;{searchQuery}&quot;
              </h3>
              <p className="text-xs text-text-muted max-w-sm">
                Try searching with a different term or clear the search to browse all files.
              </p>
            </motion.div>
          )}

          {/* File Grid / List Display */}
          {files.length > 0 && (
            <div>
              {viewMode === "grid" ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  <AnimatePresence mode="popLayout">
                    {files.map((item) => (
                      <FileItemCard
                        key={item.id}
                        item={item}
                        onOpen={handleOpenItem}
                        onRename={setActiveRenameItem}
                        onMove={setActiveMoveItem}
                        onDelete={setActiveDeleteItem}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {files.map((item) => (
                    <FileItemRow
                      key={item.id}
                      item={item}
                      onOpen={handleOpenItem}
                      onRename={setActiveRenameItem}
                      onMove={setActiveMoveItem}
                      onDelete={setActiveDeleteItem}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Modals */}
          <CreateFolderModal
            isOpen={showCreateFolder}
            onClose={() => setShowCreateFolder(false)}
            onCreate={createFolder}
          />

          <RenameModal
            isOpen={!!activeRenameItem}
            item={activeRenameItem}
            onClose={() => setActiveRenameItem(null)}
            onRename={renameItem}
          />

          <MoveModal
            isOpen={!!activeMoveItem}
            item={activeMoveItem}
            availableFolders={files.filter((f) => f.is_folder)}
            rootFolderId={breadcrumbs[0]?.id || currentFolderId || ""}
            onClose={() => setActiveMoveItem(null)}
            onMove={moveItem}
          />

          <DeleteConfirmModal
            isOpen={!!activeDeleteItem}
            item={activeDeleteItem}
            onClose={() => setActiveDeleteItem(null)}
            onDelete={deleteItem}
          />

          <PlayerModal
            file={activePlayFile}
            onClose={() => setActivePlayFile(null)}
          />
        </>
      )}
    </div>
  );
};
