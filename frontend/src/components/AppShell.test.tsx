import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders branding and storage indicator", () => {
    render(<AppShell><div>Test Content</div></AppShell>);

    expect(screen.getByText("DriveSeed")).toBeInTheDocument();
    expect(screen.getByTestId("storage-indicator")).toBeInTheDocument();
    expect(screen.getByText("Test Content")).toBeInTheDocument();
  });

  it("toggles between dark and light themes", () => {
    render(<AppShell />);

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
