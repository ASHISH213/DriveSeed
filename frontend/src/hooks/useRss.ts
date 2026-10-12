import { useCallback, useEffect, useState } from "react";
import type {
  RssCreateRequest,
  RssPreviewResult,
  RssSubscription,
  RssSyncResult,
} from "@/types/rss";

export function useRss(enabled: boolean = true) {
  const [subscriptions, setSubscriptions] = useState<RssSubscription[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSubscriptions = useCallback(async () => {
    if (!enabled) {
      setSubscriptions([]);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/rss", {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setSubscriptions([]);
          setIsLoading(false);
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to fetch RSS subscriptions: ${res.statusText}`
        );
      }

      const data = (await res.json()) as RssSubscription[];
      setSubscriptions(data);
      setError(null);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Error loading RSS subscriptions"
      );
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  const createSubscription = useCallback(
    async (payload: RssCreateRequest): Promise<RssSubscription> => {
      setError(null);
      const res = await fetch("/api/rss", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const msg =
          errData?.detail?.error?.message ||
          `Failed to create RSS subscription: ${res.statusText}`;
        setError(msg);
        throw new Error(msg);
      }

      const created = (await res.json()) as RssSubscription;
      setSubscriptions((prev) => [created, ...prev]);
      return created;
    },
    []
  );

  const deleteSubscription = useCallback(async (id: string): Promise<void> => {
    setError(null);
    const res = await fetch(`/api/rss/${id}`, {
      method: "DELETE",
    });

    if (!res.ok && res.status !== 404) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to delete RSS subscription: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    setSubscriptions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const previewFeed = useCallback(
    async (
      url: string,
      filterRegex?: string
    ): Promise<RssPreviewResult> => {
      setError(null);
      const res = await fetch("/api/rss/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          url,
          filter_regex: filterRegex || null,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const msg =
          errData?.detail?.error?.message ||
          `Failed to preview RSS feed: ${res.statusText}`;
        throw new Error(msg);
      }

      return (await res.json()) as RssPreviewResult;
    },
    []
  );

  const syncSubscription = useCallback(
    async (id: string): Promise<RssSyncResult> => {
      setError(null);
      const res = await fetch(`/api/rss/${id}/sync`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const msg =
          errData?.detail?.error?.message ||
          `Failed to sync RSS feed: ${res.statusText}`;
        throw new Error(msg);
      }

      const result = (await res.json()) as RssSyncResult;
      // Refresh list to update last_checked_at and last_item_title
      await fetchSubscriptions();
      return result;
    },
    [fetchSubscriptions]
  );

  useEffect(() => {
    void fetchSubscriptions();
  }, [fetchSubscriptions]);

  return {
    subscriptions,
    isLoading,
    error,
    fetchSubscriptions,
    createSubscription,
    deleteSubscription,
    previewFeed,
    syncSubscription,
  };
}
