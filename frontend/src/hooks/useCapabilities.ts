import { useCallback, useEffect, useState } from "react";
import type { CapabilitiesResponse } from "@/types/capabilities";

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCapabilities = useCallback(async () => {
    try {
      const res = await fetch("/api/capabilities", {
        headers: { credentials: "omit", Accept: "application/json" },
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          errData?.detail?.error?.message ||
            `Failed to fetch capabilities: ${res.statusText}`
        );
      }

      const data = (await res.json()) as CapabilitiesResponse;
      setCapabilities(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error loading capabilities");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCapabilities();
  }, [fetchCapabilities]);

  return {
    capabilities,
    isLoading,
    error,
    refetch: fetchCapabilities,
  };
}
