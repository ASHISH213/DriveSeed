import { useCallback, useEffect, useState } from "react";
import type { TelegramLinkCode, TelegramStatus } from "@/types/telegram";

export function useTelegram(enabled: boolean = true) {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!enabled) {
      setStatus(null);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/telegram/status", {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setStatus(null);
          setIsLoading(false);
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to load Telegram status: ${res.statusText}`
        );
      }

      const data = (await res.json()) as TelegramStatus;
      setStatus(data);
      setError(null);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Error loading Telegram status"
      );
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  const generateLinkCode = useCallback(async (): Promise<TelegramLinkCode> => {
    setError(null);
    const res = await fetch("/api/telegram/link-code", {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to generate Telegram link code: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    return (await res.json()) as TelegramLinkCode;
  }, []);

  const unlinkTelegram = useCallback(async (): Promise<void> => {
    setError(null);
    const res = await fetch("/api/telegram/link", {
      method: "DELETE",
    });

    if (!res.ok && res.status !== 404) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to unlink Telegram: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    setStatus((prev) => (prev ? { ...prev, is_linked: false, chat_id: null } : null));
  }, []);

  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  return {
    status,
    isLoading,
    error,
    fetchStatus,
    generateLinkCode,
    unlinkTelegram,
  };
}
