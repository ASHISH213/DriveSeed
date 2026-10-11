import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { Library } from "./Library";
import type { FileListResponse } from "@/types/library";

describe("Library", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders sign-in prompt when unauthenticated", async () => {
    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL) => {
      if (url === "/api/auth/me") {
        return {
          ok: false,
          status: 401,
          json: async () => ({}),
        } as Response;
      }
      return { ok: false, status: 404 } as Response;
    });

    render(<Library />);

    await waitFor(() => {
      expect(screen.getByText("Sign In with Google to Browse Library")).toBeInTheDocument();
    });
  });

  it("renders files and handles view toggle, navigation, and folder creation", async () => {
    const mockFilesData: FileListResponse = {
      files: [
        {
          id: "folder-1",
          name: "Movies",
          parent_id: "root-seedbox-id",
          mime_type: "application/vnd.google-apps.folder",
          size_bytes: 0,
          is_folder: true,
        },
        {
          id: "file-1",
          name: "sample_video.mp4",
          parent_id: "root-seedbox-id",
          mime_type: "video/mp4",
          size_bytes: 104857600, // 100 MB
          is_folder: false,
        },
      ],
      breadcrumbs: [
        { id: "root-seedbox-id", name: "DriveSeed Root" },
      ],
      current_folder_id: "root-seedbox-id",
    };

    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL, init?: RequestInit) => {
      const urlStr = url.toString();
      if (urlStr === "/api/auth/me") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: "user-123",
            email: "seeder@driveseed.io",
            created_at: "2026-10-11T12:00:00Z",
          }),
        } as Response;
      }

      if (urlStr.startsWith("/api/files/folder") && init?.method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: "folder-new",
            name: "Anime",
            parent_id: "root-seedbox-id",
            mime_type: "application/vnd.google-apps.folder",
            size_bytes: 0,
            is_folder: true,
          }),
        } as Response;
      }

      if (urlStr.startsWith("/api/files?folder=folder-1")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            files: [],
            breadcrumbs: [
              { id: "root-seedbox-id", name: "DriveSeed Root" },
              { id: "folder-1", name: "Movies" },
            ],
            current_folder_id: "folder-1",
          }),
        } as Response;
      }

      if (urlStr.startsWith("/api/files")) {
        return {
          ok: true,
          status: 200,
          json: async () => mockFilesData,
        } as Response;
      }

      return { ok: false, status: 404 } as Response;
    });

    render(<Library />);

    // 1. Wait for files to load
    await waitFor(() => {
      expect(screen.getByText("DriveSeed Root")).toBeInTheDocument();
      expect(screen.getByText("Movies")).toBeInTheDocument();
      expect(screen.getByText("sample_video.mp4")).toBeInTheDocument();
      expect(screen.getByText("100.0 MB")).toBeInTheDocument();
    });

    // 2. Toggle to List view
    const listBtn = screen.getByLabelText("List view");
    fireEvent.click(listBtn);
    expect(screen.getByLabelText("List view")).toBeInTheDocument();

    // 3. Click New Folder button and submit modal
    const newFolderBtn = screen.getByText("New Folder");
    fireEvent.click(newFolderBtn);

    await waitFor(() => {
      expect(screen.getByText("Create New Folder")).toBeInTheDocument();
    });

    const folderInput = screen.getByPlaceholderText("Folder name...");
    fireEvent.change(folderInput, { target: { value: "Anime" } });

    const createSubmitBtn = screen.getByRole("button", { name: "Create" });
    fireEvent.click(createSubmitBtn);

    // 4. Navigate into "Movies" folder
    const moviesFolder = screen.getByText("Movies");
    fireEvent.click(moviesFolder);

    await waitFor(() => {
      expect(screen.getByText("This folder is empty")).toBeInTheDocument();
    });
  });

  it("handles renaming and deleting an item", async () => {
    const mockFilesData: FileListResponse = {
      files: [
        {
          id: "item-to-rename",
          name: "old_name.txt",
          parent_id: "root-seedbox-id",
          mime_type: "text/plain",
          size_bytes: 1024,
          is_folder: false,
        },
      ],
      breadcrumbs: [
        { id: "root-seedbox-id", name: "DriveSeed Root" },
      ],
      current_folder_id: "root-seedbox-id",
    };

    let renameCalled = false;
    let deleteCalled = false;

    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL, init?: RequestInit) => {
      const urlStr = url.toString();
      if (urlStr === "/api/auth/me") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "user-123", email: "seeder@driveseed.io" }),
        } as Response;
      }

      if (urlStr === "/api/files/item-to-rename" && init?.method === "PATCH") {
        renameCalled = true;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: "item-to-rename",
            name: "new_name.txt",
            parent_id: "root-seedbox-id",
            mime_type: "text/plain",
            size_bytes: 1024,
            is_folder: false,
          }),
        } as Response;
      }

      if (urlStr === "/api/files/item-to-rename" && init?.method === "DELETE") {
        deleteCalled = true;
        return {
          ok: true,
          status: 200,
          json: async () => ({ success: true }),
        } as Response;
      }

      if (urlStr.startsWith("/api/files")) {
        return {
          ok: true,
          status: 200,
          json: async () => mockFilesData,
        } as Response;
      }

      return { ok: false, status: 404 } as Response;
    });

    render(<Library />);

    await waitFor(() => {
      expect(screen.getByText("old_name.txt")).toBeInTheDocument();
    });

    // Open item dropdown menu
    const moreBtn = screen.getByLabelText("File actions");
    fireEvent.click(moreBtn);

    // Click Rename
    const renameOption = screen.getByText("Rename");
    fireEvent.click(renameOption);

    await waitFor(() => {
      expect(screen.getByText("Rename File")).toBeInTheDocument();
    });

    const renameInput = screen.getByDisplayValue("old_name.txt");
    fireEvent.change(renameInput, { target: { value: "new_name.txt" } });

    const saveRenameBtn = screen.getByRole("button", { name: "Save" });
    fireEvent.click(saveRenameBtn);

    await waitFor(() => {
      expect(renameCalled).toBe(true);
    });

    // Reopen menu for delete
    const moreBtn2 = screen.getByLabelText("File actions");
    fireEvent.click(moreBtn2);

    const deleteOption = screen.getByText("Delete");
    fireEvent.click(deleteOption);

    await waitFor(() => {
      expect(screen.getByText("Delete File")).toBeInTheDocument();
    });

    const confirmDeleteBtn = screen.getByRole("button", { name: "Delete" });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(deleteCalled).toBe(true);
    });
  });
});
