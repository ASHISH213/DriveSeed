import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { WebhooksCard } from "./WebhooksCard";

describe("WebhooksCard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url, opts) => {
        const u = String(url);
        const method = opts?.method || "GET";

        if (u.endsWith("/api/webhooks") && method === "GET") {
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

  it("renders empty state when no webhooks exist", async () => {
    render(<WebhooksCard />);

    await waitFor(() => {
      expect(screen.getByText("Task Webhooks")).toBeInTheDocument();
      expect(screen.getByText("No webhooks registered")).toBeInTheDocument();
    });
  });

  it("renders active webhooks list with URLs and event badges", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/webhooks") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "wh-1",
              url: "https://my-receiver.org/hook",
              secret: "whsec_abcdef1234567890",
              events: ["task.completed", "task.failed"],
              is_active: true,
              created_at: "2026-10-12T12:00:00Z",
            },
          ],
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<WebhooksCard />);

    await waitFor(() => {
      expect(screen.getByText("https://my-receiver.org/hook")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText("task.completed")).toBeInTheDocument();
      expect(screen.getByText("task.failed")).toBeInTheDocument();
    });
  });

  it("registers a new webhook endpoint", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/webhooks") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }

      if (u.endsWith("/api/webhooks") && method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: "wh-new",
            url: "https://discord-bridge.com/events",
            secret: "whsec_custom1234",
            events: ["task.completed"],
            is_active: true,
            created_at: "2026-10-12T13:00:00Z",
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<WebhooksCard />);

    await waitFor(() => {
      expect(screen.getByTestId("add-webhook-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-webhook-btn"));

    const urlInput = screen.getByTestId("webhook-url-input");
    fireEvent.change(urlInput, {
      target: { value: "https://discord-bridge.com/events" },
    });

    fireEvent.click(screen.getByTestId("submit-create-webhook"));

    await waitFor(() => {
      expect(
        screen.getByText("https://discord-bridge.com/events")
      ).toBeInTheDocument();
    });
  });

  it("triggers test ping and displays response result", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/webhooks") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "wh-ping-test",
              url: "https://test-ping.com/hook",
              secret: "whsec_testsecret",
              events: ["task.completed"],
              is_active: true,
              created_at: "2026-10-12T12:00:00Z",
            },
          ],
        } as Response;
      }

      if (u.includes("/api/webhooks/wh-ping-test/test") && method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            success: true,
            status_code: 200,
            message: "Ping acknowledged",
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<WebhooksCard />);

    await waitFor(() => {
      expect(screen.getByTestId("test-webhook-wh-ping-test")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("test-webhook-wh-ping-test"));

    await waitFor(() => {
      expect(screen.getByTestId("test-result-wh-ping-test")).toBeInTheDocument();
      expect(
        screen.getByText("Ping delivered successfully (HTTP 200)")
      ).toBeInTheDocument();
    });
  });

  it("deletes a webhook endpoint", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/webhooks") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "wh-to-delete",
              url: "https://old-endpoint.com/hook",
              secret: "whsec_old",
              events: ["task.failed"],
              is_active: true,
              created_at: "2026-10-12T12:00:00Z",
            },
          ],
        } as Response;
      }

      if (u.includes("/api/webhooks/wh-to-delete") && method === "DELETE") {
        return {
          ok: true,
          status: 204,
          json: async () => ({}),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<WebhooksCard />);

    await waitFor(() => {
      expect(screen.getByText("https://old-endpoint.com/hook")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("delete-webhook-wh-to-delete"));

    await waitFor(() => {
      expect(
        screen.queryByText("https://old-endpoint.com/hook")
      ).not.toBeInTheDocument();
    });
  });
});
