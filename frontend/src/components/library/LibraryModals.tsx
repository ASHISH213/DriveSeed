import React, { useState } from "react";
import { FolderPlus, Edit3, FolderInput, Trash2, X, Loader2 } from "lucide-react";
import type { LibraryItem } from "@/types/library";

interface BaseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// 1. Create Folder Modal
interface CreateFolderModalProps extends BaseModalProps {
  onCreate: (name: string) => Promise<unknown>;
}

export const CreateFolderModal: React.FC<CreateFolderModalProps> = ({
  isOpen,
  onClose,
  onCreate,
}) => {
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await onCreate(name.trim());
      setName("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create folder");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl bg-bg-elevated border border-border p-5 shadow-2 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium text-text text-sm sm:text-base">
            <FolderPlus className="w-4 h-4 text-accent-1" />
            <span>Create New Folder</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-surface text-text-muted hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Folder name..."
            autoFocus
            className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-text placeholder-text-muted focus:outline-none focus:border-accent-1"
          />

          {error && <p className="text-xs text-danger">{error}</p>}

          <div className="flex items-center justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-surface text-text-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isSubmitting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-grad text-white disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Create</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 2. Rename Modal
interface RenameModalProps extends BaseModalProps {
  item: LibraryItem | null;
  onRename: (fileId: string, newName: string) => Promise<unknown>;
}

export const RenameModal: React.FC<RenameModalProps> = ({
  isOpen,
  onClose,
  item,
  onRename,
}) => {
  const [name, setName] = useState(item?.name || "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    if (item) setName(item.name);
  }, [item]);

  if (!isOpen || !item) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || isSubmitting || name.trim() === item.name) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await onRename(item.id, name.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl bg-bg-elevated border border-border p-5 shadow-2 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium text-text text-sm sm:text-base">
            <Edit3 className="w-4 h-4 text-accent-1" />
            <span>Rename {item.is_folder ? "Folder" : "File"}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-surface text-text-muted hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New name..."
            autoFocus
            className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-text placeholder-text-muted focus:outline-none focus:border-accent-1"
          />

          {error && <p className="text-xs text-danger">{error}</p>}

          <div className="flex items-center justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-surface text-text-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isSubmitting || name.trim() === item.name}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-grad text-white disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Save</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 3. Move Modal
interface MoveModalProps extends BaseModalProps {
  item: LibraryItem | null;
  availableFolders: LibraryItem[];
  rootFolderId: string;
  onMove: (fileId: string, newParentId: string) => Promise<unknown>;
}

export const MoveModal: React.FC<MoveModalProps> = ({
  isOpen,
  onClose,
  item,
  availableFolders,
  rootFolderId,
  onMove,
}) => {
  const [selectedParentId, setSelectedParentId] = useState<string>(rootFolderId);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !item) return null;

  const validTargetFolders = availableFolders.filter(
    (f) => f.is_folder && f.id !== item.id
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || selectedParentId === item.parent_id) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await onMove(item.id, selectedParentId);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to move");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl bg-bg-elevated border border-border p-5 shadow-2 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium text-text text-sm sm:text-base">
            <FolderInput className="w-4 h-4 text-accent-2" />
            <span>Move &quot;{item.name}&quot;</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-surface text-text-muted hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="text-xs text-text-muted">Select destination folder:</label>
          <select
            value={selectedParentId}
            onChange={(e) => setSelectedParentId(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-lg bg-surface border border-border text-text focus:outline-none focus:border-accent-1"
          >
            <option value={rootFolderId}>DriveSeed Root</option>
            {validTargetFolders.map((f) => (
              <option key={f.id} value={f.id}>
                📁 {f.name}
              </option>
            ))}
          </select>

          {error && <p className="text-xs text-danger">{error}</p>}

          <div className="flex items-center justify-end gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-surface text-text-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || selectedParentId === item.parent_id}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-grad text-white disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>Move</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 4. Delete Confirmation Modal
interface DeleteConfirmModalProps extends BaseModalProps {
  item: LibraryItem | null;
  onDelete: (fileId: string) => Promise<unknown>;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  onClose,
  item,
  onDelete,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !item) return null;

  const handleDelete = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onDelete(item.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl bg-bg-elevated border border-border p-5 shadow-2 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-medium text-danger text-sm sm:text-base">
            <Trash2 className="w-4 h-4 text-danger" />
            <span>Delete {item.is_folder ? "Folder" : "File"}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-surface text-text-muted hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-text-muted">
          Are you sure you want to permanently delete <strong className="text-text">{item.name}</strong> from your Google Drive? This action cannot be undone.
        </p>

        {error && <p className="text-xs text-danger">{error}</p>}

        <div className="flex items-center justify-end gap-2 mt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-surface text-text-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-danger text-white hover:opacity-90 disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>Delete</span>
          </button>
        </div>
      </div>
    </div>
  );
};
