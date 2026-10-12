import { useCallback, useEffect, useRef, useState } from "react";
import type { PlaybackInfo } from "@/types/playback";

export function usePlayback(fileId: string | null) {
  const [playbackInfo, setPlaybackInfo] = useState<PlaybackInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const pendingPositionRef = useRef<number | null>(null);
  const lastSavedPositionRef = useRef<number | null>(null);
  const saveTimeoutRef = useRef<number | null>(null);

  // Fetch initial playback position
  useEffect(() => {
    if (!fileId) {
      setPlaybackInfo(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetch(`/api/playback/${encodeURIComponent(fileId)}`, {
      headers: { Accept: "application/json" },
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Failed to load playback position: ${res.statusText}`);
        }
        return res.json() as Promise<PlaybackInfo>;
      })
      .then((data) => {
        if (isMounted) {
          setPlaybackInfo(data);
          lastSavedPositionRef.current = data.position_seconds;
        }
      })
      .catch((err: Error) => {
        if (isMounted) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [fileId]);

  // Flush pending position save to API
  const flushSave = useCallback(async () => {
    if (!fileId || pendingPositionRef.current === null) return;

    const posToSave = pendingPositionRef.current;
    pendingPositionRef.current = null;

    try {
      const res = await fetch(`/api/playback/${encodeURIComponent(fileId)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ position_seconds: posToSave }),
      });

      if (res.ok) {
        const data = (await res.json()) as PlaybackInfo;
        setPlaybackInfo(data);
        lastSavedPositionRef.current = posToSave;
      }
    } catch {
      // Non-blocking fail-soft on background save
    }
  }, [fileId]);

  // Throttled position update (e.g. called on timeupdate event)
  const savePosition = useCallback(
    (seconds: number, immediate: boolean = false) => {
      if (!fileId || seconds < 0) return;

      pendingPositionRef.current = seconds;

      if (immediate) {
        if (saveTimeoutRef.current !== null) {
          window.clearTimeout(saveTimeoutRef.current);
          saveTimeoutRef.current = null;
        }
        void flushSave();
        return;
      }

      // Throttle save requests every 4 seconds
      if (saveTimeoutRef.current === null) {
        saveTimeoutRef.current = window.setTimeout(() => {
          saveTimeoutRef.current = null;
          void flushSave();
        }, 4000);
      }
    },
    [fileId, flushSave]
  );

  // Clear playback position (e.g. video ended)
  const clearPosition = useCallback(async () => {
    if (!fileId) return;

    if (saveTimeoutRef.current !== null) {
      window.clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    pendingPositionRef.current = null;

    try {
      await fetch(`/api/playback/${encodeURIComponent(fileId)}`, {
        method: "DELETE",
      });
      setPlaybackInfo({
        file_id: fileId,
        position_seconds: 0,
        updated_at: null,
      });
      lastSavedPositionRef.current = 0;
    } catch {
      // Fail-soft
    }
  }, [fileId]);

  // Flush on unmount if any pending save
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current !== null) {
        window.clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
      if (pendingPositionRef.current !== null) {
        void flushSave();
      }
    };
  }, [flushSave]);

  return {
    playbackInfo,
    isLoading,
    error,
    savePosition,
    clearPosition,
  };
}
