import { useEffect, useRef, useState } from "react";
import type { TaskEvent } from "@/types/task";

interface UseEventsOptions {
  enabled?: boolean;
  onEvent?: (event: TaskEvent) => void;
}

export function useEvents({ enabled = true, onEvent }: UseEventsOptions = {}) {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return;
    }

    let eventSource: EventSource | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let isDisposed = false;

    function connect() {
      if (isDisposed) return;

      try {
        eventSource = new EventSource("/events");

        eventSource.onopen = () => {
          if (!isDisposed) setIsConnected(true);
        };

        eventSource.addEventListener("task_update", (e: MessageEvent) => {
          if (isDisposed) return;
          try {
            const data = JSON.parse(e.data) as TaskEvent;
            onEventRef.current?.(data);
          } catch (err) {
            console.warn("Failed to parse SSE task_update event:", err);
          }
        });

        eventSource.onerror = () => {
          if (!isDisposed) {
            setIsConnected(false);
            if (eventSource) {
              eventSource.close();
              eventSource = null;
            }
            // Attempt auto-reconnect after 3 seconds
            reconnectTimeout = setTimeout(connect, 3000);
          }
        };
      } catch (err) {
        console.warn("Failed to initialize EventSource:", err);
        if (!isDisposed) {
          setIsConnected(false);
          reconnectTimeout = setTimeout(connect, 3000);
        }
      }
    }

    connect();

    return () => {
      isDisposed = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      setIsConnected(false);
    };
  }, [enabled]);

  return { isConnected };
}
