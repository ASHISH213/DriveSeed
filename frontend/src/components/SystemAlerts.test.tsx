import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { SystemAlerts } from "./SystemAlerts";
import type { StorageQuota } from "@/types/storage";

describe("SystemAlerts", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders offline alert when navigator is offline", () => {
    // Simulate offline
    vi.stubGlobal("navigator", { onLine: false });

    render(<SystemAlerts />);

    expect(screen.getByTestId("offline-alert")).toBeInTheDocument();
    expect(screen.getByText(/You are currently offline/i)).toBeInTheDocument();
  });

  it("renders drive full alert when free_bytes is 0", async () => {
    vi.stubGlobal("navigator", { onLine: true });

    // Mock auth user
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/auth/me")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ id: "user-1", email: "user@example.com" }),
          });
        }
        if (url.includes("/api/storage")) {
          const fullStorage: StorageQuota = {
            used_bytes: 15 * 1024 * 1024 * 1024,
            total_bytes: 15 * 1024 * 1024 * 1024,
            free_bytes: 0,
            percent_used: 100.0,
          };
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => fullStorage,
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
      })
    );

    render(<SystemAlerts />);

    const alert = await screen.findByTestId("drive-full-alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText(/Google Drive Storage Full \(0 B Free\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Manage Drive/i)).toBeInTheDocument();
  });

  it("renders drive almost full alert when percent_used is >= 90% and allows dismissal", async () => {
    vi.stubGlobal("navigator", { onLine: true });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/auth/me")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ id: "user-1", email: "user@example.com" }),
          });
        }
        if (url.includes("/api/storage")) {
          const almostFullStorage: StorageQuota = {
            used_bytes: 14 * 1024 * 1024 * 1024,
            total_bytes: 15 * 1024 * 1024 * 1024,
            free_bytes: 1 * 1024 * 1024 * 1024,
            percent_used: 93.3,
          };
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => almostFullStorage,
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
      })
    );

    render(<SystemAlerts />);

    const alert = await screen.findByTestId("drive-almost-full-alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText(/Drive Storage Almost Full \(93.3%\)/i)).toBeInTheDocument();

    // Dismiss warning
    const dismissBtn = screen.getByLabelText("Dismiss warning");
    fireEvent.click(dismissBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("drive-almost-full-alert")).not.toBeInTheDocument();
    });
  });

  it("renders drive disconnected alert when storage returns disconnected error", async () => {
    vi.stubGlobal("navigator", { onLine: true });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/auth/me")) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ id: "user-1", email: "user@example.com" }),
          });
        }
        if (url.includes("/api/storage")) {
          return Promise.resolve({
            ok: false,
            status: 400,
            json: async () => ({
              detail: { error: { code: "drive_disconnected", message: "Drive disconnected" } },
            }),
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
      })
    );

    render(<SystemAlerts />);

    const alert = await screen.findByTestId("drive-disconnected-alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText(/Google Drive Disconnected/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reconnect drive/i })).toBeInTheDocument();
  });
});
