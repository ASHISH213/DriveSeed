import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { ApiTokensCard } from "./ApiTokensCard";

describe("ApiTokensCard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url, opts) => {
        const u = String(url);
        const method = opts?.method || "GET";

        if (u.endsWith("/api/tokens") && method === "GET") {
          return {
            ok: true,
            status: 200,
            json: async () => [],
          } as Response;
        }

        return {
          ok: false,
          status: 404,
          json: async () => ({}),
        } as Response;
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state when no tokens exist", async () => {
    render(<ApiTokensCard />);

    await waitFor(() => {
      expect(screen.getByText("Personal API Tokens")).toBeInTheDocument();
      expect(screen.getByText("No API tokens generated")).toBeInTheDocument();
    });
  });

  it("renders table of active tokens with prefixes", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/tokens") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "token-1",
              prefix: "ds_abc1234",
              label: "Home Media Server",
              created_at: "2026-10-12T10:00:00Z",
              last_used_at: null,
            },
          ],
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<ApiTokensCard />);

    await waitFor(() => {
      expect(screen.getByText("Home Media Server")).toBeInTheDocument();
      expect(screen.getByText("ds_abc1234...")).toBeInTheDocument();
      expect(screen.getByText("Never")).toBeInTheDocument();
    });
  });

  it("creates a token and reveals the raw secret in a modal", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/tokens") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }

      if (u.endsWith("/api/tokens") && method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: "new-token-id",
            prefix: "ds_xyz9876",
            label: "Curl Client",
            created_at: "2026-10-12T11:00:00Z",
            last_used_at: null,
            token: "ds_xyz9876543210abcdefghijklmnop",
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<ApiTokensCard />);

    await waitFor(() => {
      expect(screen.getByTestId("create-token-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("create-token-btn"));

    // Modal input
    expect(screen.getByTestId("create-token-modal")).toBeInTheDocument();
    const input = screen.getByTestId("token-label-input");
    fireEvent.change(input, { target: { value: "Curl Client" } });

    fireEvent.click(screen.getByTestId("submit-create-token"));

    // Modal reveals secret token
    await waitFor(() => {
      expect(screen.getByTestId("revealed-token-modal")).toBeInTheDocument();
      expect(
        screen.getByText("ds_xyz9876543210abcdefghijklmnop")
      ).toBeInTheDocument();
      expect(screen.getByText("Copy your token now!")).toBeInTheDocument();
    });

    // Dismiss reveal modal
    fireEvent.click(screen.getByTestId("close-revealed-modal"));
    await waitFor(() => {
      expect(screen.queryByTestId("revealed-token-modal")).not.toBeInTheDocument();
    });
  });

  it("revokes a token when delete button is clicked", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/tokens") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "token-to-delete",
              prefix: "ds_del123",
              label: "Obsolete Script",
              created_at: "2026-10-12T10:00:00Z",
              last_used_at: null,
            },
          ],
        } as Response;
      }

      if (u.includes("/api/tokens/token-to-delete") && method === "DELETE") {
        return {
          ok: true,
          status: 204,
          json: async () => ({}),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<ApiTokensCard />);

    await waitFor(() => {
      expect(screen.getByText("Obsolete Script")).toBeInTheDocument();
    });

    const revokeBtn = screen.getByTestId("revoke-token-token-to-delete");
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(screen.queryByText("Obsolete Script")).not.toBeInTheDocument();
    });
  });
});
