import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { TelegramCard } from "./TelegramCard";

describe("TelegramCard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url, opts) => {
        const u = String(url);
        const method = opts?.method || "GET";

        if (u.endsWith("/api/telegram/status") && method === "GET") {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              is_linked: false,
              chat_id: null,
              bot_username: "DriveSeedBot",
            }),
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

  it("renders unlinked state with Connect button and command list", async () => {
    render(<TelegramCard />);

    await waitFor(() => {
      expect(screen.getByText("Telegram Bot")).toBeInTheDocument();
      expect(screen.getByTestId("telegram-unlinked-status")).toBeInTheDocument();
      expect(screen.getByTestId("connect-telegram-btn")).toBeInTheDocument();
      expect(screen.getByText("/add <magnet|url>")).toBeInTheDocument();
      expect(screen.getByText("/status")).toBeInTheDocument();
      expect(screen.getByText("/library")).toBeInTheDocument();
    });
  });

  it("renders linked state with chat ID and Disconnect button", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/telegram/status") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            is_linked: true,
            chat_id: "88990011",
            bot_username: "DriveSeedBot",
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<TelegramCard />);

    await waitFor(() => {
      expect(screen.getByTestId("telegram-linked-status")).toBeInTheDocument();
      expect(screen.getByText("Chat ID: 88990011")).toBeInTheDocument();
      expect(screen.getByTestId("unlink-telegram-btn")).toBeInTheDocument();
    });
  });

  it("opens connect modal and generates link code", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/telegram/status") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            is_linked: false,
            chat_id: null,
            bot_username: "DriveSeedBot",
          }),
        } as Response;
      }

      if (u.endsWith("/api/telegram/link-code") && method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            code: "A1B2C3",
            bot_username: "DriveSeedBot",
            deep_link: "https://t.me/DriveSeedBot?start=A1B2C3",
            expires_in_seconds: 600,
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<TelegramCard />);

    await waitFor(() => {
      expect(screen.getByTestId("connect-telegram-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("connect-telegram-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("telegram-link-code-display")).toBeInTheDocument();
      expect(screen.getByText("A1B2C3")).toBeInTheDocument();
      expect(screen.getByTestId("copy-code-btn")).toBeInTheDocument();
      expect(screen.getByTestId("open-telegram-btn")).toBeInTheDocument();
    });
  });

  it("disconnects Telegram account when Disconnect is clicked", async () => {
    vi.stubGlobal("confirm", () => true);

    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/telegram/status") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            is_linked: true,
            chat_id: "77889900",
            bot_username: "DriveSeedBot",
          }),
        } as Response;
      }

      if (u.endsWith("/api/telegram/link") && method === "DELETE") {
        return {
          ok: true,
          status: 204,
          json: async () => ({}),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<TelegramCard />);

    await waitFor(() => {
      expect(screen.getByTestId("unlink-telegram-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("unlink-telegram-btn"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/telegram/link",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });
});
