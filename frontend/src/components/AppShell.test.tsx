import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders branding and sign-in button when unauthenticated", async () => {
    // Mock /api/auth/me -> 401 Unauthorized
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: { error: { code: "unauthorized" } } }),
    } as Response);

    render(<AppShell><div>Test Content</div></AppShell>);

    expect(screen.getByText("DriveSeed")).toBeInTheDocument();
    expect(screen.getByTestId("storage-indicator")).toBeInTheDocument();
    expect(screen.getByText("Test Content")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("login-button")).toBeInTheDocument();
      expect(screen.getByText("Sign in with Google")).toBeInTheDocument();
    });
  });

  it("renders user email and logout button when authenticated", async () => {
    // Mock /api/auth/me -> 200 OK with User data
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        id: "550e8400-e29b-41d4-a716-446655440000",
        email: "testuser@driveseed.io",
        created_at: "2026-10-11T12:00:00Z",
      }),
    } as Response);

    render(<AppShell />);

    await waitFor(() => {
      expect(screen.getByTestId("user-profile")).toBeInTheDocument();
      expect(screen.getByText("testuser@driveseed.io")).toBeInTheDocument();
      expect(screen.getByTestId("logout-button")).toBeInTheDocument();
    });

    // Logout click
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    } as Response);

    fireEvent.click(screen.getByTestId("logout-button"));

    await waitFor(() => {
      expect(screen.getByTestId("login-button")).toBeInTheDocument();
    });
  });

  it("toggles between dark and light themes", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({}),
    } as Response);

    render(<AppShell />);

    await waitFor(() => {
      expect(screen.getByTestId("login-button")).toBeInTheDocument();
    });

    const toggleButton = screen.getByTestId("theme-toggle");

    // Initially dark (no data-theme attribute on root)
    expect(document.documentElement.getAttribute("data-theme")).toBeNull();

    // Click to toggle to light theme
    fireEvent.click(toggleButton);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("driveseed-theme")).toBe("light");

    // Click again to toggle back to dark theme
    fireEvent.click(toggleButton);
    expect(document.documentElement.getAttribute("data-theme")).toBeNull();
    expect(localStorage.getItem("driveseed-theme")).toBe("dark");
  });
});
