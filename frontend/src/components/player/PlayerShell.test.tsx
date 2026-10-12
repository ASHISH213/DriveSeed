import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { PlayerShell } from "./PlayerShell";

describe("PlayerShell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    // Mock HTMLMediaElement methods in jsdom
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => Promise.resolve());
    window.HTMLMediaElement.prototype.pause = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders video element, controls, and file title", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        file_id: "vid-1",
        position_seconds: 0,
        updated_at: null,
      }),
    } as Response);

    render(
      <PlayerShell
        fileId="vid-1"
        fileName="BigBuckBunny.mp4"
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("BigBuckBunny.mp4")).toBeInTheDocument();
    });
    expect(screen.getByTestId("player-shell")).toBeInTheDocument();
    expect(screen.getByTestId("play-pause-btn")).toBeInTheDocument();

    const video = screen.getByTestId("player-shell").querySelector("video");
    expect(video).toBeInTheDocument();
    expect(video).toHaveAttribute("src", "/stream/vid-1");
  });

  it("toggles play and pause on button click", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        file_id: "vid-1",
        position_seconds: 0,
        updated_at: null,
      }),
    } as Response);

    render(
      <PlayerShell
        fileId="vid-1"
        fileName="BigBuckBunny.mp4"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("play-pause-btn")).toBeInTheDocument();
    });
    const playBtn = screen.getByTestId("play-pause-btn");
    fireEvent.click(playBtn);
    expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalled();
  });

  it("displays resume prompt when saved position is greater than 5 seconds", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        file_id: "vid-resume",
        position_seconds: 120, // 2 minutes
        updated_at: "2026-10-12T00:00:00Z",
      }),
    } as Response);

    render(
      <PlayerShell
        fileId="vid-resume"
        fileName="SavedMovie.mp4"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("resume-prompt")).toBeInTheDocument();
      expect(screen.getByText("Resume Playback?")).toBeInTheDocument();
      expect(screen.getByText("2:00")).toBeInTheDocument();
    });

    // Clicking "Resume" seeks to 120s and hides prompt
    const resumeBtn = screen.getByRole("button", { name: "Resume" });
    fireEvent.click(resumeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("resume-prompt")).not.toBeInTheDocument();
    });
  });

  it("handles restarting from beginning when resume prompt is declined", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        file_id: "vid-restart",
        position_seconds: 350,
        updated_at: "2026-10-12T00:00:00Z",
      }),
    } as Response);

    // Mock DELETE request for clearPosition
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    } as Response);

    render(
      <PlayerShell
        fileId="vid-restart"
        fileName="SavedMovie.mp4"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("resume-prompt")).toBeInTheDocument();
    });

    const restartBtn = screen.getByRole("button", { name: "Start from beginning" });
    fireEvent.click(restartBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("resume-prompt")).not.toBeInTheDocument();
    });
  });

  it("handles keyboard shortcuts (Space, Arrow keys, Mute, Subtitles)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        file_id: "vid-kb",
        position_seconds: 0,
        updated_at: null,
      }),
    } as Response);

    render(
      <PlayerShell
        fileId="vid-kb"
        fileName="ShortcutsMovie.mp4"
      />
    );

    // Space key to play
    fireEvent.keyDown(window, { code: "Space" });
    expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalled();

    // Key M to toggle mute
    fireEvent.keyDown(window, { code: "KeyM" });
    await waitFor(() => {
      expect(screen.getByText("Muted")).toBeInTheDocument();
    });

    // Key C to toggle captions
    fireEvent.keyDown(window, { code: "KeyC" });
    await waitFor(() => {
      expect(screen.getByText("Subtitles: Enabled")).toBeInTheDocument();
    });
  });

  it("loads subtitle tracks, displays menu, and activates WebVTT track", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/subtitles")) {
        return {
          ok: true,
          json: async () => ({
            subtitles: [
              {
                id: "sub-1",
                name: "Movie.en.srt",
                label: "English",
                language: "en",
                format: "srt",
              },
              {
                id: "sub-2",
                name: "Movie.es.vtt",
                label: "Spanish",
                language: "es",
                format: "vtt",
              },
            ],
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({
          file_id: "vid-subs",
          position_seconds: 0,
          updated_at: null,
        }),
      } as Response;
    });

    render(<PlayerShell fileId="vid-subs" fileName="Movie.mp4" />);

    // Click subtitles button to open dropdown menu
    const subBtn = await waitFor(() => screen.getByTestId("subtitles-btn"));
    fireEvent.click(subBtn);

    // Verify subtitle menu renders with available tracks
    expect(await screen.findByTestId("subtitles-menu")).toBeInTheDocument();
    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Spanish")).toBeInTheDocument();

    // Click English track
    fireEvent.click(screen.getByText("English"));

    // Verify track element was added to video
    await waitFor(() => {
      const trackEl = document.querySelector("track");
      expect(trackEl).toBeInTheDocument();
      expect(trackEl?.getAttribute("src")).toContain("/api/files/vid-subs/subtitles/sub-1");
      expect(trackEl?.getAttribute("srclang")).toBe("en");
      expect(trackEl?.getAttribute("label")).toBe("English");
    });

    // Test cycling with KeyC to next track (Spanish)
    fireEvent.keyDown(window, { code: "KeyC" });
    await waitFor(() => {
      const trackEl = document.querySelector("track");
      expect(trackEl?.getAttribute("src")).toContain("/api/files/vid-subs/subtitles/sub-2");
      expect(trackEl?.getAttribute("label")).toBe("Spanish");
    });
  });
});

