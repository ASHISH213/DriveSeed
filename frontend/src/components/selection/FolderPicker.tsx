import React, { useEffect, useState } from "react";
import { Folder, ChevronDown, Check, FolderRoot, Loader2 } from "lucide-react";
import type { LibraryItem } from "@/types/library";

interface FolderPickerProps {
  selectedFolderId: string | null;
  onSelectFolder: (folderId: string | null, folderName: string) => void;
}

export const FolderPicker: React.FC<FolderPickerProps> = ({
  selectedFolderId,
  onSelectFolder,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [folders, setFolders] = useState<LibraryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedName, setSelectedName] = useState<string>("DriveSeed (Root)");

  // Load user's top-level folders from DriveSeed
  useEffect(() => {
    let active = true;

    async function loadFolders() {
      setIsLoading(true);
      try {
        const res = await fetch("/api/files");
        if (res.ok && active) {
          const data = await res.json();
          // Filter only items that are folders
          const folderItems: LibraryItem[] = (data.files || []).filter(
            (item: LibraryItem) => item.is_folder
          );
          setFolders(folderItems);

          if (selectedFolderId) {
            const found = folderItems.find((f) => f.id === selectedFolderId);
            if (found) {
              setSelectedName(`DriveSeed / ${found.name}`);
            }
          }
        }
      } catch (err) {
        console.warn("Could not load folders for FolderPicker:", err);
      } finally {
        if (active) setIsLoading(false);
      }
    }

    void loadFolders();
    return () => {
      active = false;
    };
  }, [selectedFolderId]);

  const handleSelect = (folderId: string | null, name: string) => {
    onSelectFolder(folderId, name);
    setSelectedName(name);
    setIsOpen(false);
  };

  return (
    <div className="relative w-full text-xs">
      <label className="block text-text-muted mb-1.5 font-medium">
        Destination Drive Folder
      </label>

      {/* Selector Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-surface border border-border hover:bg-surface-hover text-text transition-colors text-left"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Folder className="w-4 h-4 text-accent-1 flex-shrink-0" />
          <span className="truncate font-medium">{selectedName}</span>
        </div>
        <ChevronDown
          className={`w-3.5 h-3.5 text-text-muted transition-transform flex-shrink-0 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Folder Dropdown / List */}
      {isOpen && (
        <div className="absolute left-0 right-0 z-30 mt-1 max-h-48 overflow-y-auto rounded-lg bg-bg-elevated border border-border shadow-2 divide-y divide-border/40 scrollbar-thin">
          {/* Default Root Option */}
          <button
            type="button"
            onClick={() => handleSelect(null, "DriveSeed (Root)")}
            className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-surface transition-colors ${
              selectedFolderId === null ? "text-accent-1 font-medium bg-accent-1/5" : "text-text"
            }`}
          >
            <div className="flex items-center gap-2">
              <FolderRoot className="w-4 h-4 text-accent-1" />
              <span>DriveSeed (Root folder)</span>
            </div>
            {selectedFolderId === null && <Check className="w-3.5 h-3.5 text-accent-1" />}
          </button>

          {/* Subfolders */}
          {isLoading ? (
            <div className="p-3 text-center text-text-muted flex items-center justify-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Loading folders...</span>
            </div>
          ) : folders.length === 0 ? (
            <div className="p-2.5 text-center text-text-muted text-[11px]">
              No custom subfolders found in DriveSeed
            </div>
          ) : (
            folders.map((folder) => {
              const isSelected = selectedFolderId === folder.id;
              return (
                <button
                  key={folder.id}
                  type="button"
                  onClick={() => handleSelect(folder.id, `DriveSeed / ${folder.name}`)}
                  className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-surface transition-colors ${
                    isSelected ? "text-accent-1 font-medium bg-accent-1/5" : "text-text"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Folder className="w-4 h-4 text-accent-2 flex-shrink-0" />
                    <span className="truncate">{folder.name}</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-accent-1 flex-shrink-0" />}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
