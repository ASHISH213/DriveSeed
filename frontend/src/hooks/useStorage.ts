import { useCallback, useEffect, useState } from "react";
import type { StorageQuota } from "@/types/storage";

export function useStorage(enabled: boolean = true) {
  const [storage, setStorage] = useState<StorageQuota | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStorage = useCallback(async () => {
    if (!enabled) {
      setStorage(null);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/storage", {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setStorage(null);
          setIsLoading(false);
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to fetch storage: ${res.statusText}`
        );
      }

      const data = (await res.json()) as StorageQuota;
      setStorage(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error loading storage");
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void fetchStorage();

    if (!enabled) return;

    // Refresh quota every 30 seconds
    const interval = window.setInterval(() => {
      void fetchStorage();
    }, 30000);

    return () => window.clearInterval(interval);
  }, [fetchStorage, enabled]);

  return {
    storage,
    isLoading,
    error,
    refetch: fetchStorage,
  };
}
