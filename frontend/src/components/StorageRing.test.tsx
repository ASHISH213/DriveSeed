import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { StorageRing } from "./StorageRing";
import type { StorageQuota } from "@/types/storage";

describe("StorageRing", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders connecting label when loading", () => {
    render(<StorageRing isLoading={true} storage={null} />);

    expect(screen.getByTestId("storage-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("storage-ring")).toBeInTheDocument();
    expect(screen.getByTestId("storage-label")).toHaveTextContent("Connecting...");
  });

  it("renders disconnected state when drive error is present", () => {
    render(<StorageRing error="Drive disconnected" storage={null} isLoading={false} />);

    expect(screen.getByTestId("storage-label")).toHaveTextContent("Drive Disconnected");
  });

  it("renders success state for normal usage under 75%", () => {
    const mockStorage: StorageQuota = {
      used_bytes: 3 * 1024 * 1024 * 1024, // 3 GB
      total_bytes: 15 * 1024 * 1024 * 1024, // 15 GB
      free_bytes: 12 * 1024 * 1024 * 1024,
      percent_used: 20.0,
    };

    render(<StorageRing storage={mockStorage} isLoading={false} error={null} />);

    const label = screen.getByTestId("storage-label");
    expect(label).toHaveTextContent("3.0 GB / 15.0 GB");

    const circle = screen.getByTestId("storage-ring").querySelector("path.text-success");
    expect(circle).toBeInTheDocument();
  });

  it("renders warning state for usage between 75% and 89%", () => {
    const mockStorage: StorageQuota = {
      used_bytes: 12 * 1024 * 1024 * 1024, // 12 GB
      total_bytes: 15 * 1024 * 1024 * 1024, // 15 GB
      free_bytes: 3 * 1024 * 1024 * 1024,
      percent_used: 80.0,
    };

    render(<StorageRing storage={mockStorage} isLoading={false} error={null} />);

    const circle = screen.getByTestId("storage-ring").querySelector("path.text-warning");
    expect(circle).toBeInTheDocument();
  });

  it("renders danger state and warning alert for usage at or above 90%", () => {
    const mockStorage: StorageQuota = {
      used_bytes: 14.5 * 1024 * 1024 * 1024,
      total_bytes: 15 * 1024 * 1024 * 1024,
      free_bytes: 0.5 * 1024 * 1024 * 1024,
      percent_used: 96.7,
    };

    render(<StorageRing storage={mockStorage} isLoading={false} error={null} />);

    const circle = screen.getByTestId("storage-ring").querySelector("path.text-danger");
    expect(circle).toBeInTheDocument();

    // Hover to trigger popover
    const indicator = screen.getByTestId("storage-indicator");
    fireEvent.mouseEnter(indicator.parentElement!);

    expect(screen.getByTestId("storage-popover")).toBeInTheDocument();
    expect(screen.getByText("Drive is nearly full. Clean up space or upgrade Drive.")).toBeInTheDocument();
  });

  it("shows storage breakdown in popover on hover", () => {
    const mockStorage: StorageQuota = {
      used_bytes: 5 * 1024 * 1024 * 1024,
      total_bytes: 15 * 1024 * 1024 * 1024,
      free_bytes: 10 * 1024 * 1024 * 1024,
      percent_used: 33.3,
    };

    render(<StorageRing storage={mockStorage} isLoading={false} error={null} />);

    const indicator = screen.getByTestId("storage-indicator");
    fireEvent.mouseEnter(indicator.parentElement!);

    expect(screen.getByTestId("storage-popover")).toBeInTheDocument();
    expect(screen.getByText("33.3%")).toBeInTheDocument();
    expect(screen.getByText("Used:")).toBeInTheDocument();
    expect(screen.getByText("Free Space:")).toBeInTheDocument();
    expect(screen.getByText("Total Capacity:")).toBeInTheDocument();
  });
});
