import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { FileSelectionModal } from "./FileSelectionModal";
import type { Task } from "@/types/task";
import type { StorageQuota } from "@/types/storage";

describe("FileSelectionModal", () => {
  const mockStorageQuota: StorageQuota = {
    used_bytes: 5 * 1024 * 1024 * 1024,
    total_bytes: 15 * 1024 * 1024 * 1024,
    free_bytes: 10 * 1024 * 1024 * 1024, // 10 GB free
    percent_used: 33.3,
  };

  const sampleTask: Task = {
    id: "task-abc",
    user_id: "user-1",
    source_type: "magnet",
    source_uri: "magnet:?xt=urn:btih:multi123",
    info_hash: "multi123",
    name: "Big Movie Bundle (1080p)",
    state: "awaiting_selection",
    progress: 0.0,
    size_bytes: 3 * 1024 * 1024 * 1024,
    error: null,
    created_at: "2026-10-12T10:00:00Z",
    completed_at: null,
    files: [
      {
        id: "file-1",
        task_id: "task-abc",
        path: "Movie.Part1.mp4",
        size_bytes: 1024 * 1024 * 1024, // 1 GB
        selected: true,
        state: "pending",
        drive_file_id: null,
      },
      {
        id: "file-2",
        task_id: "task-abc",
        path: "Movie.Part2.mp4",
        size_bytes: 2 * 1024 * 1024 * 1024, // 2 GB
        selected: true,
        state: "pending",
        drive_file_id: null,
      },
      {
        id: "file-3",
        task_id: "task-abc",
        path: "Extras/Subtitles.srt",
        size_bytes: 50 * 1024, // 50 KB
        selected: true,
        state: "pending",
        drive_file_id: null,
      },
    ],
  };

  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/storage")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => mockStorageQuota,
          });
        }
        if (url.includes("/api/files")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              current_folder_id: "root-123",
              breadcrumbs: [{ id: "root-123", name: "DriveSeed" }],
              files: [
                {
                  id: "folder-movies",
                  name: "Movies",
                  parent_id: "root-123",
                  mime_type: "application/vnd.google-apps.folder",
                  is_folder: true,
                  size_bytes: 0,
                },
              ],
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({}),
        });
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders modal with file list, checkboxes, and Drive storage check", async () => {
    const onStart = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <FileSelectionModal
        isOpen={true}
        task={sampleTask}
        onClose={onClose}
        onStart={onStart}
      />
    );

    expect(screen.getByText("Select Files to Download")).toBeInTheDocument();
    expect(screen.getByText("Big Movie Bundle (1080p)")).toBeInTheDocument();
    expect(screen.getByText("Movie.Part1.mp4")).toBeInTheDocument();
    expect(screen.getByText("Movie.Part2.mp4")).toBeInTheDocument();
    expect(screen.getByText("Subtitles.srt")).toBeInTheDocument();

    // Verify storage quota loads and displays Space Verified
    await waitFor(() => {
      expect(screen.getByText("Space Verified")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /start download/i })).not.toBeDisabled();
  });

  it("deselecting a file updates the total selected size dynamically", async () => {
    const onStart = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <FileSelectionModal
        isOpen={true}
        task={sampleTask}
        onClose={onClose}
        onStart={onStart}
      />
    );

    // Initial total: ~3.0 GB selected (3 of 3 files)
    await waitFor(() => {
      expect(screen.getByTestId("selected-summary")).toHaveTextContent("3 of 3 files selected");
    });
    expect(screen.getByTestId("selected-summary")).toHaveTextContent("3.0 GB");

    // Toggle off Movie.Part2 (2 GB)
    const file2Btn = screen.getByLabelText("Select Movie.Part2.mp4");
    fireEvent.click(file2Btn);

    // Total should now be 2 of 3 files selected (~1.0 GB)
    await waitFor(() => {
      expect(screen.getByTestId("selected-summary")).toHaveTextContent("2 of 3 files selected");
    });
    expect(screen.getByTestId("selected-summary")).toHaveTextContent("1.0 GB");

    // Deselect All
    fireEvent.click(screen.getByRole("button", { name: "Deselect All" }));
    await waitFor(() => {
      expect(screen.getByTestId("selected-summary")).toHaveTextContent("0 of 3 files selected");
    });

    // Start button should be disabled when 0 files selected
    expect(screen.getByRole("button", { name: /start download/i })).toBeDisabled();

    // Select All
    fireEvent.click(screen.getByRole("button", { name: "Select All" }));
    await waitFor(() => {
      expect(screen.getByTestId("selected-summary")).toHaveTextContent("3 of 3 files selected");
    });
  });

  it("disables start button and shows warning if Drive space is insufficient", async () => {
    // Override storage quota with tiny free space (100 MB free)
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/storage")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              used_bytes: 14.9 * 1024 * 1024 * 1024,
              total_bytes: 15 * 1024 * 1024 * 1024,
              free_bytes: 100 * 1024 * 1024, // 100 MB free < 3 GB required
              percent_used: 99.3,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ files: [] }),
        });
      })
    );

    const onStart = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <FileSelectionModal
        isOpen={true}
        task={sampleTask}
        onClose={onClose}
        onStart={onStart}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Insufficient Google Drive Storage")).toBeInTheDocument();
    });

    const startBtn = screen.getByRole("button", { name: /start download/i });
    expect(startBtn).toBeDisabled();
  });

  it("submits selected file IDs and folder on start confirmation", async () => {
    const onStart = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <FileSelectionModal
        isOpen={true}
        task={sampleTask}
        onClose={onClose}
        onStart={onStart}
      />
    );

    // Deselect file-2
    fireEvent.click(screen.getByLabelText("Select Movie.Part2.mp4"));

    const startBtn = screen.getByRole("button", { name: /start download/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(onStart).toHaveBeenCalledWith("task-abc", {
        selected_file_ids: expect.arrayContaining(["file-1", "file-3"]),
        destination_folder_id: null,
      });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("closes modal on cancel click or escape key", () => {
    const onStart = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <FileSelectionModal
        isOpen={true}
        task={sampleTask}
        onClose={onClose}
        onStart={onStart}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
