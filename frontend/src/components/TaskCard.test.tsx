import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TaskCard } from "./TaskCard";
import type { Task } from "@/types/task";

describe("TaskCard", () => {
  const baseTask: Task = {
    id: "task-1234",
    user_id: "user-1",
    source_type: "magnet",
    source_uri: "magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=archlinux.iso",
    info_hash: "da39a3ee5e6b4b0d3255bfef95601890afd80709",
    name: "archlinux.iso",
    state: "downloading",
    progress: 0.654,
    size_bytes: 1_000_000_000,
    speed_bps: 2_500_000,
    downloaded_bytes: 654_000_000,
    total_bytes: 1_000_000_000,
    eta_seconds: 138,
    error: null,
    files: [],
    created_at: "2026-10-11T12:00:00Z",
    completed_at: null,
  };

  it("renders downloading task with speed, percentage, and pause button", async () => {
    const onPause = vi.fn().mockResolvedValue(undefined);
    const onCancel = vi.fn().mockResolvedValue(undefined);

    render(<TaskCard task={baseTask} onPause={onPause} onCancel={onCancel} />);

    expect(screen.getByText("archlinux.iso")).toBeInTheDocument();
    expect(screen.getByText("Downloading")).toBeInTheDocument();
    expect(screen.getByText("65.4%")).toBeInTheDocument();
    expect(screen.getByText("2.4 MB/s")).toBeInTheDocument();
    expect(screen.getByText("~2m 18s")).toBeInTheDocument();

    const pauseBtn = screen.getByLabelText("Pause task");
    expect(pauseBtn).toBeInTheDocument();
    fireEvent.click(pauseBtn);
    await waitFor(() => {
      expect(onPause).toHaveBeenCalledWith("task-1234");
    });

    const cancelBtn = screen.getByLabelText("Cancel task");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    await waitFor(() => {
      expect(onCancel).toHaveBeenCalledWith("task-1234");
    });
  });

  it("renders paused task with play/resume button", async () => {
    const onResume = vi.fn().mockResolvedValue(undefined);
    const pausedTask: Task = { ...baseTask, state: "paused" };

    render(<TaskCard task={pausedTask} onResume={onResume} />);

    expect(screen.getByText("Paused")).toBeInTheDocument();
    const resumeBtn = screen.getByLabelText("Resume task");
    expect(resumeBtn).toBeInTheDocument();
    fireEvent.click(resumeBtn);
    await waitFor(() => {
      expect(onResume).toHaveBeenCalledWith("task-1234");
    });
  });

  it("renders completed task badge", () => {
    const completedTask: Task = { ...baseTask, state: "completed", progress: 1.0 };
    render(<TaskCard task={completedTask} />);

    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
  });

  it("renders failed task error alert with retry button and triggers onRetry", async () => {
    const onRetry = vi.fn().mockResolvedValue(undefined);
    const failedTask: Task = {
      ...baseTask,
      state: "failed",
      error: "Google Drive storage quota exceeded",
    };
    render(<TaskCard task={failedTask} onRetry={onRetry} />);

    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Google Drive storage quota exceeded")).toBeInTheDocument();

    const retryBtn = screen.getByLabelText("Retry task button");
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(onRetry).toHaveBeenCalledWith("task-1234");
    });
  });

  it("renders Stream Now button for downloading task and triggers onStream", () => {
    const onStream = vi.fn();
    render(<TaskCard task={baseTask} onStream={onStream} />);

    const streamBtn = screen.getByTestId("stream-now-btn");
    expect(streamBtn).toBeInTheDocument();
    expect(screen.getByText("Stream Now")).toBeInTheDocument();

    fireEvent.click(streamBtn);
    expect(onStream).toHaveBeenCalledWith(baseTask);
  });
});

