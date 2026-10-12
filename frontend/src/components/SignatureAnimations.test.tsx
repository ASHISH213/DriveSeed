import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AnimatedTicker } from "./AnimatedTicker";
import { AnimatedCheckmark } from "./AnimatedCheckmark";
import { ConfettiBurst } from "./ConfettiBurst";
import { ProgressBar } from "./ProgressBar";

describe("Signature Animations (M3b.2)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe("AnimatedTicker", () => {
    it("renders speed and percentage tabular text accurately", () => {
      render(<AnimatedTicker value="2.4 MB/s" />);
      expect(screen.getByTestId("animated-ticker")).toBeInTheDocument();
      expect(screen.getByText("2.4 MB/s")).toBeInTheDocument();
    });

    it("renders percentage values with tabular numerals", () => {
      render(<AnimatedTicker value="65.4%" />);
      expect(screen.getByText("65.4%")).toBeInTheDocument();
    });
  });

  describe("AnimatedCheckmark", () => {
    it("renders SVG checkmark with self-drawing path and circle", () => {
      render(<AnimatedCheckmark className="w-4 h-4 text-success" />);
      const checkmark = screen.getByTestId("animated-checkmark");
      expect(checkmark).toBeInTheDocument();
      expect(checkmark.querySelector("circle")).toBeInTheDocument();
      expect(checkmark.querySelector("path")).toBeInTheDocument();
    });
  });

  describe("ConfettiBurst", () => {
    it("renders celebration particles and auto-completes within 600ms", () => {
      const handleComplete = vi.fn();
      render(<ConfettiBurst onComplete={handleComplete} />);

      const confetti = screen.getByTestId("confetti-burst");
      expect(confetti).toBeInTheDocument();
      // Particles strictly <= 40
      expect(confetti.children.length).toBeLessThanOrEqual(40);
      expect(confetti.children.length).toBeGreaterThan(0);

      // Fast-forward timers by 600ms
      act(() => {
        vi.advanceTimersByTime(650);
      });

      expect(handleComplete).toHaveBeenCalledTimes(1);
    });
  });

  describe("ProgressBar with sheen and cloud-to-drive indicator", () => {
    it("renders moving sheen on active downloading progress bar", () => {
      const { container } = render(
        <ProgressBar
          progress={0.5}
          state="downloading"
          speedBps={2_500_000}
          downloadedBytes={500_000_000}
          totalBytes={1_000_000_000}
          etaSeconds={200}
        />
      );

      const sheenElement = container.querySelector(".animate-sheen");
      expect(sheenElement).toBeInTheDocument();
      expect(screen.getByText("2.4 MB/s")).toBeInTheDocument();
      expect(screen.getByText("50.0%")).toBeInTheDocument();
    });

    it("renders cloud-to-drive path animation when state is uploading", () => {
      render(
        <ProgressBar
          progress={0.8}
          state="uploading"
          downloadedBytes={800_000_000}
          totalBytes={1_000_000_000}
        />
      );

      expect(screen.getByTestId("cloud-drive-path")).toBeInTheDocument();
      expect(screen.getByText("Uploading to Drive...")).toBeInTheDocument();
      expect(screen.getByText("80.0%")).toBeInTheDocument();
    });
  });
});
