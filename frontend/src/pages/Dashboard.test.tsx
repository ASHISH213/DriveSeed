import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { Dashboard } from "./Dashboard";
import type { Task } from "@/types/task";

interface MockEventSourceInstance {
  url: string;
  emit: (event: string, data: unknown) => void;
  close: () => void;
}

describe("Dashboard", () => {
  let mockEventSourceInstances: MockEventSourceInstance[] = [];

  beforeEach(() => {
    mockEventSourceInstances = [];
    vi.stubGlobal("fetch", vi.fn());

    // Mock global EventSource
    class MockEventSource implements MockEventSourceInstance {
      listeners: Record<string, ((e: { data: string }) => void)[]> = {};
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(public url: string) {
        mockEventSourceInstances.push(this);
        setTimeout(() => {
          if (this.onopen) this.onopen();
        }, 10);
      }

      addEventListener(event: string, cb: (e: { data: string }) => void) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(cb);
      }

      emit(event: string, data: unknown) {
        const cbs = this.listeners[event] || [];
        for (const cb of cbs) {
          cb({ data: JSON.stringify(data) });
        }
      }

      close() {}
    }

    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state when user has no active tasks", async () => {
    // 1. Mock /api/auth/me
    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL) => {
      if (url === "/api/auth/me") {
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
      if (url === "/api/tasks") {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }
      return { ok: false, status: 404 } as Response;
    });

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("No active downloads")).toBeInTheDocument();
      expect(screen.getByLabelText("Download source URI")).toBeInTheDocument();
    });
  });

  it("renders active tasks and updates progress via live SSE event", async () => {
    const initialTask: Task = {
      id: "task-sse-1",
      user_id: "user-123",
      source_type: "url",
      source_uri: "https://example.com/bigfile.bin",
      info_hash: null,
      name: "bigfile.bin",
      state: "downloading",
      progress: 0.1,
      size_bytes: 1_000_000_000,
      speed_bps: 1_000_000,
      downloaded_bytes: 100_000_000,
      total_bytes: 1_000_000_000,
      eta_seconds: 900,
      error: null,
      files: [],
      created_at: "2026-10-11T12:00:00Z",
      completed_at: null,
    };

    vi.mocked(fetch).mockImplementation(async (url: RequestInfo | URL) => {
      if (url === "/api/auth/me") {
        return {
          ok: true,
          status: 200,
          json: async () => ({ id: "user-123", email: "seeder@driveseed.io" }),
        } as Response;
      }
      if (url === "/api/tasks") {
        return {
          ok: true,
          status: 200,
          json: async () => [initialTask],
        } as Response;
      }
      return { ok: false, status: 404 } as Response;
    });

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText("bigfile.bin")).toBeInTheDocument();
      expect(screen.getByText("10.0%")).toBeInTheDocument();
    });

    // Simulate incoming SSE event updating task to 75%
    expect(mockEventSourceInstances.length).toBeGreaterThan(0);
    const es = mockEventSourceInstances[0];

    act(() => {
      es.emit("task_update", {
        task_id: "task-sse-1",
        user_id: "user-123",
        name: "bigfile.bin",
        state: "downloading",
        progress: 0.75,
        speed_bps: 5_000_000,
        downloaded_bytes: 750_000_000,
        total_bytes: 1_000_000_000,
        error: null,
        timestamp: Date.now(),
      });
    });

    await waitFor(() => {
      expect(screen.getByText("75.0%")).toBeInTheDocument();
      expect(screen.getByText("4.8 MB/s")).toBeInTheDocument();
    });
  });
});
