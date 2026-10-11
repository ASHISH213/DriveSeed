import { useCallback, useEffect, useState } from "react";
import type { BreadcrumbItem, FileListResponse, LibraryItem, ViewMode } from "@/types/library";

export function useLibrary(userLoggedIn: boolean = true) {
  const [files, setFiles] = useState<LibraryItem[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([
    { id: "root", name: "DriveSeed" },
  ]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [viewMode, setViewModeState] = useState<ViewMode>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("driveseed-library-view") as ViewMode | null;
      if (saved === "grid" || saved === "list") return saved;
    }
    return "grid";
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const setViewMode = (mode: ViewMode) => {
    setViewModeState(mode);
    localStorage.setItem("driveseed-library-view", mode);
  };

  const fetchFiles = useCallback(
    async (folderId: string | null = null, search: string = "") => {
      if (!userLoggedIn) {
        setFiles([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        if (folderId) params.set("folder", folderId);
        if (search.trim()) params.set("search", search.trim());

        const res = await fetch(`/api/files?${params.toString()}`, {
          headers: { Accept: "application/json" },
        });

        if (!res.ok) {
          if (res.status === 401) {
            setFiles([]);
            return;
          }
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody?.detail?.error?.message || `Failed to fetch files: ${res.statusText}`);
        }

        const data = (await res.json()) as FileListResponse;
        setFiles(data.files);
        setCurrentFolderId(data.current_folder_id);

        // Update breadcrumbs root ID if it was placeholder
        if (data.breadcrumbs && data.breadcrumbs.length > 0) {
          setBreadcrumbs((prev) => {
            // If at root level, adopt backend breadcrumbs
            if (!folderId || data.current_folder_id === data.breadcrumbs[0].id) {
              return data.breadcrumbs;
            }
            // Keep local trail if folder was clicked
            const existingIdx = prev.findIndex((b) => b.id === data.current_folder_id);
            if (existingIdx !== -1) {
              return prev.slice(0, existingIdx + 1);
            }
            return data.breadcrumbs;
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading files");
      } finally {
        setIsLoading(false);
      }
    },
    [userLoggedIn]
  );

  useEffect(() => {
    fetchFiles(currentFolderId, searchQuery);
  }, [fetchFiles, currentFolderId, searchQuery]);

  const navigateToFolder = (folderId: string, folderName?: string) => {
    setSearchQuery("");
    if (folderName) {
      setBreadcrumbs((prev) => {
        const existingIdx = prev.findIndex((b) => b.id === folderId);
        if (existingIdx !== -1) {
          return prev.slice(0, existingIdx + 1);
        }
        return [...prev, { id: folderId, name: folderName }];
      });
    }
    setCurrentFolderId(folderId);
  };

  const createFolder = async (name: string): Promise<LibraryItem> => {
    const res = await fetch("/api/files/folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_id: currentFolderId || undefined }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody?.detail?.error?.message || "Failed to create folder");
    }

    const created = (await res.json()) as LibraryItem;
    // Add to current file list and sort (folders first)
    setFiles((prev) => [created, ...prev.filter((f) => f.id !== created.id)]);
    return created;
  };

  const renameItem = async (fileId: string, newName: string): Promise<LibraryItem> => {
    const res = await fetch(`/api/files/${fileId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody?.detail?.error?.message || "Failed to rename item");
    }

    const updated = (await res.json()) as LibraryItem;
    setFiles((prev) => prev.map((f) => (f.id === fileId ? updated : f)));
    return updated;
  };

  const moveItem = async (fileId: string, newParentId: string): Promise<LibraryItem> => {
    const res = await fetch(`/api/files/${fileId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_id: newParentId }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody?.detail?.error?.message || "Failed to move item");
    }

    const updated = (await res.json()) as LibraryItem;
    // Remove from current folder view
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
    return updated;
  };

  const deleteItem = async (fileId: string): Promise<void> => {
    const res = await fetch(`/api/files/${fileId}`, { method: "DELETE" });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody?.detail?.error?.message || "Failed to delete item");
    }
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  return {
    files,
    breadcrumbs,
    currentFolderId,
    searchQuery,
    setSearchQuery,
    viewMode,
    setViewMode,
    isLoading,
    error,
    refreshLibrary: () => fetchFiles(currentFolderId, searchQuery),
    navigateToFolder,
    createFolder,
    renameItem,
    moveItem,
    deleteItem,
  };
}
