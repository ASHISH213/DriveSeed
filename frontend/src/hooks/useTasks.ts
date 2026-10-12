import { useCallback, useEffect, useState } from "react";
import type { Task, TaskCreateRequest, TaskEvent, TaskStartRequest } from "@/types/task";
import { useEvents } from "./useEvents";

export function useTasks(userLoggedIn: boolean = true) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!userLoggedIn) {
      setTasks([]);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/tasks", {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        if (res.status === 401) {
          setTasks([]);
          return;
        }
        throw new Error(`Failed to fetch tasks: ${res.statusText}`);
      }
      const data = (await res.json()) as Task[];
      setTasks(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error fetching tasks");
    } finally {
      setIsLoading(false);
    }
  }, [userLoggedIn]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Handle incoming live SSE events
  const handleEvent = useCallback((event: TaskEvent) => {
    setTasks((prev) => {
      const index = prev.findIndex((t) => t.id === event.task_id);
      if (index === -1) {
        // If task not yet in state, fetch tasks to get complete record
        fetchTasks();
        return prev;
      }

      const existing = prev[index];
      const remainingBytes =
        event.total_bytes && event.downloaded_bytes
          ? Math.max(0, event.total_bytes - event.downloaded_bytes)
          : null;
      const etaSeconds =
        event.speed_bps && event.speed_bps > 0 && remainingBytes !== null
          ? Math.round(remainingBytes / event.speed_bps)
          : null;

      const updated: Task = {
        ...existing,
        state: event.state,
        progress: event.progress,
        name: event.name || existing.name,
        speed_bps: event.speed_bps,
        downloaded_bytes: event.downloaded_bytes,
        total_bytes: event.total_bytes || existing.size_bytes || 0,
        eta_seconds: etaSeconds,
        error: event.error ?? existing.error,
        completed_at: event.state === "completed" ? new Date().toISOString() : existing.completed_at,
      };

      const copy = [...prev];
      copy[index] = updated;
      return copy;
    });
  }, [fetchTasks]);

  const { isConnected: isSseConnected } = useEvents({
    enabled: userLoggedIn,
    onEvent: handleEvent,
  });

  const createTask = async (req: TaskCreateRequest): Promise<Task> => {
    setError(null);
    const res = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const msg = errBody?.detail?.error?.message || errBody?.detail || "Failed to create task";
      throw new Error(msg);
    }

    const created = (await res.json()) as Task;
    // Optimistically prepend to tasks list
    setTasks((prev) => [created, ...prev.filter((t) => t.id !== created.id)]);
    return created;
  };

  const startTask = async (taskId: string, req?: TaskStartRequest): Promise<Task> => {
    setError(null);
    const res = await fetch(`/api/tasks/${taskId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req || {}),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const msg = errBody?.detail?.error?.message || errBody?.detail || "Failed to start task";
      throw new Error(msg);
    }

    const updated = (await res.json()) as Task;
    setTasks((prev) => prev.map((t) => (t.id === taskId ? updated : t)));
    return updated;
  };

  const pauseTask = async (taskId: string) => {
    const res = await fetch(`/api/tasks/${taskId}/pause`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to pause task");
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, state: "paused", speed_bps: 0 } : t))
    );
  };

  const resumeTask = async (taskId: string) => {
    const res = await fetch(`/api/tasks/${taskId}/resume`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to resume task");
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, state: "downloading" } : t))
    );
  };

  const cancelTask = async (taskId: string) => {
    const res = await fetch(`/api/tasks/${taskId}/cancel`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to cancel task");
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, state: "cancelled", speed_bps: 0 } : t))
    );
  };

  return {
    tasks,
    isLoading,
    error,
    isSseConnected,
    refreshTasks: fetchTasks,
    createTask,
    startTask,
    pauseTask,
    resumeTask,
    cancelTask,
  };
}
