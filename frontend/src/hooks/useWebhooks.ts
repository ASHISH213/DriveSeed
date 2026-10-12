import { useCallback, useEffect, useState } from "react";
import type {
  WebhookCreateRequest,
  WebhookEndpoint,
  WebhookTestResult,
} from "@/types/webhook";

export function useWebhooks(enabled: boolean = true) {
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWebhooks = useCallback(async () => {
    if (!enabled) {
      setWebhooks([]);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/webhooks", {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setWebhooks([]);
          setIsLoading(false);
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to fetch webhooks: ${res.statusText}`
        );
      }

      const data = (await res.json()) as WebhookEndpoint[];
      setWebhooks(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error loading webhooks");
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  const createWebhook = useCallback(
    async (payload: WebhookCreateRequest): Promise<WebhookEndpoint> => {
      setError(null);
      const res = await fetch("/api/webhooks", {
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
          `Failed to create webhook: ${res.statusText}`;
        setError(msg);
        throw new Error(msg);
      }

      const created = (await res.json()) as WebhookEndpoint;
      setWebhooks((prev) => [created, ...prev]);
      return created;
    },
    []
  );

  const deleteWebhook = useCallback(async (id: string): Promise<void> => {
    setError(null);
    const res = await fetch(`/api/webhooks/${id}`, {
      method: "DELETE",
    });

    if (!res.ok && res.status !== 404) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to delete webhook: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    setWebhooks((prev) => prev.filter((w) => w.id !== id));
  }, []);

  const testWebhook = useCallback(
    async (id: string): Promise<WebhookTestResult> => {
      setError(null);
      const res = await fetch(`/api/webhooks/${id}/test`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const msg =
          errData?.detail?.error?.message ||
          `Failed to trigger test ping: ${res.statusText}`;
        return {
          success: false,
          status_code: res.status,
          message: msg,
        };
      }

      return (await res.json()) as WebhookTestResult;
    },
    []
  );

  useEffect(() => {
    void fetchWebhooks();
  }, [fetchWebhooks]);

  return {
    webhooks,
    isLoading,
    error,
    createWebhook,
    deleteWebhook,
    testWebhook,
    refresh: fetchWebhooks,
  };
}
