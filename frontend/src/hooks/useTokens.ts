import { useCallback, useEffect, useState } from "react";
import type { ApiToken, ApiTokenCreated } from "@/types/token";

export function useTokens(enabled: boolean = true) {
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTokens = useCallback(async () => {
    if (!enabled) {
      setTokens([]);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/tokens", {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setTokens([]);
          setIsLoading(false);
          return;
        }
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to fetch API tokens: ${res.statusText}`
        );
      }

      const data = (await res.json()) as ApiToken[];
      setTokens(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error loading tokens");
    } finally {
      setIsLoading(false);
    }
  }, [enabled]);

  const createToken = useCallback(async (label: string): Promise<ApiTokenCreated> => {
    setError(null);
    const res = await fetch("/api/tokens", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ label }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to create API token: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    const created = (await res.json()) as ApiTokenCreated;
    setTokens((prev) => [created, ...prev]);
    return created;
  }, []);

  const revokeToken = useCallback(async (id: string): Promise<void> => {
    setError(null);
    const res = await fetch(`/api/tokens/${id}`, {
      method: "DELETE",
    });

    if (!res.ok && res.status !== 404) {
      const errData = await res.json().catch(() => ({}));
      const msg =
        errData?.detail?.error?.message ||
        `Failed to revoke API token: ${res.statusText}`;
      setError(msg);
      throw new Error(msg);
    }

    setTokens((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    void fetchTokens();
  }, [fetchTokens]);

  return {
    tokens,
    isLoading,
    error,
    createToken,
    revokeToken,
    refresh: fetchTokens,
  };
}
