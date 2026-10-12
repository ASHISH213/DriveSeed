import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { CommandPalette } from "./CommandPalette";
import { AppShell } from "./AppShell";

describe("CommandPalette", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders command palette items when open", () => {
    const handleClose = vi.fn();
    const handleNavigate = vi.fn();

    render(
      <CommandPalette
        isOpen={true}
        onClose={handleClose}
        onNavigateTab={handleNavigate}
        isDarkTheme={true}
      />
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search downloads, files/i)).toBeInTheDocument();
    expect(screen.getByText("Go to Downloads")).toBeInTheDocument();
    expect(screen.getByText("Go to Drive Library")).toBeInTheDocument();
  });

  it("filters items as query is typed", () => {
    const handleClose = vi.fn();
    const handleNavigate = vi.fn();

    render(
      <CommandPalette
        isOpen={true}
        onClose={handleClose}
        onNavigateTab={handleNavigate}
        isDarkTheme={true}
      />
    );

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "library" } });

    expect(screen.getByText("Go to Drive Library")).toBeInTheDocument();
    expect(screen.queryByText("Go to Downloads")).not.toBeInTheDocument();
  });

  it("navigates selection with arrow keys and executes on enter", () => {
    const handleClose = vi.fn();
    const handleNavigate = vi.fn();

    render(
      <CommandPalette
        isOpen={true}
        onClose={handleClose}
        onNavigateTab={handleNavigate}
        isDarkTheme={true}
      />
    );

    const input = screen.getByRole("textbox");

    // Press ArrowDown to select second item ("Go to Drive Library")
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleNavigate).toHaveBeenCalledWith("library");
    expect(handleClose).toHaveBeenCalled();
  });

  it("closes palette on escape key and backdrop click", () => {
    const handleClose = vi.fn();
    const handleNavigate = vi.fn();

    const { rerender } = render(
      <CommandPalette
        isOpen={true}
        onClose={handleClose}
        onNavigateTab={handleNavigate}
      />
    );

    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Backdrop click
    const backdrop = screen.getByTestId("command-palette-backdrop");
    fireEvent.click(backdrop);
    expect(handleClose).toHaveBeenCalledTimes(2);

    // When closed, dialog is not rendered
    rerender(
      <CommandPalette
        isOpen={false}
        onClose={handleClose}
        onNavigateTab={handleNavigate}
      />
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens palette from AppShell via Ctrl+K and button trigger", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({}),
    } as Response);

    render(<AppShell />);

    // Initially closed
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Trigger via header button
    const trigger = screen.getByTestId("command-palette-trigger");
    fireEvent.click(trigger);

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Close via escape
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    // Trigger via Ctrl+K keyboard shortcut
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
