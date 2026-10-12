import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  RotateCcw,
  RotateCw,
  X,
  HelpCircle,
  Subtitles,
  Gauge,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { formatTime } from "@/lib/format";
import { usePlayback } from "@/hooks/usePlayback";

export interface PlayerShellProps {
  fileId: string;
  fileName: string;
  mimeType?: string;
  onClose?: () => void;
}

interface RippleState {
  side: "left" | "right";
  text: string;
  timestamp: number;
}

export const PlayerShell: React.FC<PlayerShellProps> = ({
  fileId,
  fileName,
  onClose,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const scrubBarRef = useRef<HTMLDivElement>(null);

  // Playback persistence hook
  const { playbackInfo, savePosition, clearPosition } = usePlayback(fileId);

  // Player state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [bufferedPercent, setBufferedPercent] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false);
  const [captionsActive, setCaptionsActive] = useState(false);

  // UX & Animation state
  const [showControls, setShowControls] = useState(true);
  const [isBuffering, setIsBuffering] = useState(false);
  const [playerError, setPlayerError] = useState<string | null>(null);
  const [resumePrompt, setResumePrompt] = useState<{
    position: number;
  } | null>(null);
  const [ripple, setRipple] = useState<RippleState | null>(null);
  const [hoverScrub, setHoverScrub] = useState<{
    percent: number;
    time: number;
  } | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const idleTimerRef = useRef<number | null>(null);
  const clickTimerRef = useRef<number | null>(null);
  const hasPromptedResumeRef = useRef(false);

  // Toast auto-dismiss
  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((curr) => (curr === msg ? null : curr));
    }, 2000);
  }, []);

  // Idle controls hiding timer (fade after 2.5s idle)
  const resetIdleTimer = useCallback(() => {
    setShowControls(true);
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current);
    }
    if (isPlaying) {
      idleTimerRef.current = window.setTimeout(() => {
        setShowControls(false);
        setShowSpeedMenu(false);
      }, 2500);
    }
  }, [isPlaying]);

  useEffect(() => {
    resetIdleTimer();
    return () => {
      if (idleTimerRef.current !== null) {
        window.clearTimeout(idleTimerRef.current);
      }
    };
  }, [resetIdleTimer]);

  // Check saved resume position when playbackInfo is loaded
  useEffect(() => {
    if (
      playbackInfo &&
      playbackInfo.position_seconds > 5 &&
      !hasPromptedResumeRef.current
    ) {
      hasPromptedResumeRef.current = true;
      setResumePrompt({ position: playbackInfo.position_seconds });
    }
  }, [playbackInfo]);

  // Video event listeners
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration || 0);
      setPlayerError(null);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const curr = videoRef.current.currentTime;
      setCurrentTime(curr);
      savePosition(curr);

      // Calculate buffered progress
      if (videoRef.current.buffered.length > 0 && videoRef.current.duration > 0) {
        const bufferedEnd = videoRef.current.buffered.end(
          videoRef.current.buffered.length - 1
        );
        setBufferedPercent(
          Math.min(100, (bufferedEnd / videoRef.current.duration) * 100)
        );
      }
    }
  };

  const handlePlay = () => {
    setIsPlaying(true);
    setIsBuffering(false);
    resetIdleTimer();
  };

  const handlePause = () => {
    setIsPlaying(false);
    setShowControls(true);
    if (videoRef.current) {
      savePosition(videoRef.current.currentTime, true);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setShowControls(true);
    void clearPosition();
  };

  const handleWaiting = () => setIsBuffering(true);
  const handlePlaying = () => setIsBuffering(false);

  const handleError = async () => {
    setIsBuffering(false);
    try {
      const res = await fetch(`/api/stream/${fileId}`, {
        headers: { Range: "bytes=0-0" },
      });
      if (res.status === 429) {
        const body = (await res.json().catch(() => null)) as
          | { error?: { message?: string } }
          | null;
        setPlayerError(
          body?.error?.message ||
            "Maximum concurrent stream limit reached. Please pause or close another active stream."
        );
        return;
      }
      if (res.status === 403) {
        setPlayerError("Media streaming is disabled in this environment.");
        return;
      }
      if (res.status === 404) {
        setPlayerError("Media file was not found in storage.");
        return;
      }
    } catch {
      // Network or parsing error fallback
    }
    setPlayerError(
      "Unable to stream media. The file format may require transcoding or is unavailable."
    );
  };

  // Play / Pause toggle
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => {});
    } else {
      videoRef.current.pause();
    }
  }, []);

  // Seek relative
  const seekRelative = useCallback(
    (delta: number) => {
      if (!videoRef.current) return;
      const target = Math.max(
        0,
        Math.min(videoRef.current.duration || 0, videoRef.current.currentTime + delta)
      );
      videoRef.current.currentTime = target;
      setCurrentTime(target);
      savePosition(target, true);

      // Trigger skip ripple
      setRipple({
        side: delta < 0 ? "left" : "right",
        text: delta < 0 ? `${delta}s` : `+${delta}s`,
        timestamp: Date.now(),
      });
      setTimeout(() => setRipple(null), 600);
      resetIdleTimer();
    },
    [savePosition, resetIdleTimer]
  );

  // Direct scrub seek
  const handleScrub = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrubBarRef.current || !videoRef.current || !duration) return;
    const rect = scrubBarRef.current.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const target = pos * duration;
    videoRef.current.currentTime = target;
    setCurrentTime(target);
    savePosition(target, true);
  };

  const handleScrubHover = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrubBarRef.current || !duration) return;
    const rect = scrubBarRef.current.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    setHoverScrub({
      percent: percent * 100,
      time: percent * duration,
    });
  };

  // Volume
  const changeVolume = useCallback((newVol: number) => {
    if (!videoRef.current) return;
    const clamped = Math.max(0, Math.min(1, newVol));
    videoRef.current.volume = clamped;
    videoRef.current.muted = clamped === 0;
    setVolume(clamped);
    setIsMuted(clamped === 0);
  }, []);

  const toggleMute = useCallback(() => {
    if (!videoRef.current) return;
    const willMute = !isMuted;
    videoRef.current.muted = willMute;
    setIsMuted(willMute);
    showToast(willMute ? "Muted" : "Unmuted");
  }, [isMuted, showToast]);

  // Fullscreen
  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      await containerRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      await document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  // Playback Rate
  const changeSpeed = (rate: number) => {
    if (!videoRef.current) return;
    videoRef.current.playbackRate = rate;
    setPlaybackRate(rate);
    setShowSpeedMenu(false);
    showToast(`${rate}x Speed`);
  };

  // Resume Prompt actions
  const handleAcceptResume = () => {
    if (resumePrompt && videoRef.current) {
      videoRef.current.currentTime = resumePrompt.position;
      setCurrentTime(resumePrompt.position);
      videoRef.current.play().catch(() => {});
    }
    setResumePrompt(null);
  };

  const handleRestartResume = () => {
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      setCurrentTime(0);
      void clearPosition();
      videoRef.current.play().catch(() => {});
    }
    setResumePrompt(null);
  };

  // Double click vs Single click on video frame
  const handleVideoAreaClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // If clicked on controls, ignore
    if ((e.target as HTMLElement).closest(".player-controls")) return;

    if (clickTimerRef.current) {
      // Double click detected
      window.clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
      const rect = e.currentTarget.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      if (clickX < rect.width / 2) {
        seekRelative(-10);
      } else {
        seekRelative(10);
      }
    } else {
      // Single click - wait briefly to distinguish from double click
      clickTimerRef.current = window.setTimeout(() => {
        clickTimerRef.current = null;
        togglePlay();
      }, 250);
    }
  };

  // Keyboard Shortcuts handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.code) {
        case "Space":
        case "KeyK":
          e.preventDefault();
          togglePlay();
          break;
        case "ArrowLeft":
        case "KeyJ":
          e.preventDefault();
          seekRelative(-10);
          break;
        case "ArrowRight":
        case "KeyL":
          e.preventDefault();
          seekRelative(10);
          break;
        case "ArrowUp":
          e.preventDefault();
          changeVolume(volume + 0.1);
          break;
        case "ArrowDown":
          e.preventDefault();
          changeVolume(volume - 0.1);
          break;
        case "KeyF":
          e.preventDefault();
          void toggleFullscreen();
          break;
        case "KeyM":
          e.preventDefault();
          toggleMute();
          break;
        case "KeyC":
          e.preventDefault();
          setCaptionsActive((prev) => {
            const next = !prev;
            showToast(next ? "Subtitles: Enabled" : "Subtitles: Off");
            return next;
          });
          break;
        case "Escape":
          if (!document.fullscreenElement && onClose) {
            e.preventDefault();
            onClose();
          }
          break;
      }
      resetIdleTimer();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    togglePlay,
    seekRelative,
    changeVolume,
    volume,
    toggleFullscreen,
    toggleMute,
    onClose,
    resetIdleTimer,
    showToast,
  ]);

  const streamSrc = `/stream/${encodeURIComponent(fileId)}`;
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div
      ref={containerRef}
      onMouseMove={resetIdleTimer}
      onTouchStart={resetIdleTimer}
      className="relative w-full h-full bg-black flex flex-col items-center justify-center overflow-hidden select-none"
      data-testid="player-shell"
    >
      {/* Ambient background glow */}
      <div className="absolute inset-0 bg-gradient-radial from-accent-1/10 via-transparent to-transparent pointer-events-none" />

      {/* Main Video Element */}
      <div
        className="relative w-full h-full flex items-center justify-center cursor-pointer"
        onClick={handleVideoAreaClick}
      >
        <video
          ref={videoRef}
          src={streamSrc}
          className="max-w-full max-h-full object-contain"
          playsInline
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onPlay={handlePlay}
          onPause={handlePause}
          onEnded={handleEnded}
          onWaiting={handleWaiting}
          onPlaying={handlePlaying}
          onError={handleError}
        />

        {/* Double-tap / click skip ripple feedback */}
        <AnimatePresence>
          {ripple && (
            <motion.div
              key={ripple.timestamp}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1.1 }}
              exit={{ opacity: 0, scale: 1.3 }}
              transition={{ duration: 0.4 }}
              className={`absolute top-1/2 -translate-y-1/2 flex flex-col items-center justify-center w-28 h-28 rounded-full bg-surface-hover/80 backdrop-blur-md border border-white/20 text-white font-mono font-semibold pointer-events-none ${
                ripple.side === "left" ? "left-12 sm:left-24" : "right-12 sm:right-24"
              }`}
            >
              {ripple.side === "left" ? (
                <RotateCcw className="w-8 h-8 text-accent-2 mb-1" />
              ) : (
                <RotateCw className="w-8 h-8 text-accent-1 mb-1" />
              )}
              <span className="text-sm">{ripple.text}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Buffering Spinner */}
        {isBuffering && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="p-4 rounded-2xl bg-black/50 backdrop-blur-md border border-white/10 flex items-center gap-3 text-white">
              <Loader2 className="w-6 h-6 animate-spin text-accent-2" />
              <span className="text-xs font-medium">Buffering stream...</span>
            </div>
          </div>
        )}

        {/* Media Error Overlay */}
        {playerError && (
          <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center p-6 text-center z-30">
            <div className="w-12 h-12 rounded-full bg-danger/10 text-danger flex items-center justify-center mb-3">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-text mb-1">Playback Error</h3>
            <p className="text-xs text-text-muted max-w-md mb-4">{playerError}</p>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-surface border border-border text-xs font-semibold text-text hover:bg-surface-hover transition-colors"
              >
                Close Player
              </button>
            )}
          </div>
        )}
      </div>

      {/* Floating Toast Notification */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute top-16 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full bg-surface-hover/90 backdrop-blur-md border border-border text-xs font-medium text-white shadow-glow pointer-events-none z-40"
          >
            {toastMessage}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Resume Prompt Modal */}
      <AnimatePresence>
        {resumePrompt && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="absolute bottom-24 left-1/2 -translate-x-1/2 w-11/12 max-w-md p-4 rounded-xl bg-bg-elevated/95 backdrop-blur-xl border border-accent-1/40 shadow-glow flex flex-col gap-3 z-40 player-controls"
            data-testid="resume-prompt"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RotateCw className="w-4 h-4 text-accent-1" />
                <span className="text-xs font-semibold text-white">Resume Playback?</span>
              </div>
              <button
                type="button"
                onClick={() => setResumePrompt(null)}
                className="text-text-muted hover:text-white transition-colors"
                aria-label="Dismiss resume prompt"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-xs text-text-muted">
              You previously stopped watching at{" "}
              <span className="font-mono text-accent-2 font-semibold">
                {formatTime(resumePrompt.position)}
              </span>
              . Would you like to resume from where you left off?
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={handleRestartResume}
                className="px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-medium text-text-muted hover:text-white hover:bg-surface-hover transition-colors"
              >
                Start from beginning
              </button>
              <button
                type="button"
                onClick={handleAcceptResume}
                className="px-4 py-1.5 rounded-lg bg-accent-grad text-white text-xs font-semibold shadow-glow hover:opacity-95 transition-opacity"
              >
                Resume
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Keyboard Shortcuts Help Dialog */}
      <AnimatePresence>
        {showShortcutsHelp && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-50 player-controls"
            onClick={() => setShowShortcutsHelp(false)}
          >
            <div
              className="w-full max-w-sm rounded-xl bg-bg-elevated border border-border p-5 flex flex-col gap-4 shadow-2"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-white">Keyboard Shortcuts</h4>
                <button
                  type="button"
                  onClick={() => setShowShortcutsHelp(false)}
                  className="p-1 rounded-md text-text-muted hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Play / Pause</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    Space / K
                  </kbd>
                </div>
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Seek ±10s</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    ← / → / J / L
                  </kbd>
                </div>
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Volume ±10%</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    ↑ / ↓
                  </kbd>
                </div>
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Fullscreen</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    F
                  </kbd>
                </div>
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Mute toggle</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    M
                  </kbd>
                </div>
                <div className="flex justify-between p-2 rounded bg-surface border border-border">
                  <span className="text-text-muted">Subtitles</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-bg border border-border text-accent-2">
                    C
                  </kbd>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Top Header Bar */}
      <AnimatePresence>
        {showControls && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.2 }}
            className="absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 via-black/40 to-transparent flex items-center justify-between z-30 player-controls"
          >
            <div className="flex items-center gap-3">
              {onClose && (
                <button
                  type="button"
                  onClick={onClose}
                  className="p-2 rounded-lg bg-surface/80 hover:bg-surface-hover backdrop-blur-md border border-white/10 text-white transition-colors"
                  aria-label="Close player"
                  title="Close (Esc)"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <h2 className="text-sm font-semibold text-white truncate max-w-md">
                {fileName}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowShortcutsHelp(true)}
                className="p-2 rounded-lg bg-surface/80 hover:bg-surface-hover backdrop-blur-md border border-white/10 text-text-muted hover:text-white transition-colors"
                title="Keyboard Shortcuts"
                aria-label="Keyboard Shortcuts"
              >
                <HelpCircle className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Controls Bar */}
      <AnimatePresence>
        {showControls && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex flex-col gap-2 z-30 player-controls"
          >
            {/* Timeline Scrub Bar */}
            <div
              ref={scrubBarRef}
              onClick={handleScrub}
              onMouseMove={handleScrubHover}
              onMouseLeave={() => setHoverScrub(null)}
              className="relative w-full h-3 flex items-center cursor-pointer group"
              data-testid="player-scrub-bar"
            >
              {/* Background Track */}
              <div className="w-full h-1 group-hover:h-2 rounded-full bg-white/20 transition-all overflow-hidden relative">
                {/* Buffered Progress */}
                <div
                  className="absolute top-0 bottom-0 left-0 bg-white/30 transition-all"
                  style={{ width: `${bufferedPercent}%` }}
                />
                {/* Played Progress */}
                <div
                  className="absolute top-0 bottom-0 left-0 bg-accent-grad shadow-glow transition-all"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              {/* Scrubber Knob */}
              <div
                className="absolute w-3.5 h-3.5 rounded-full bg-white shadow-glow transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ left: `${progressPercent}%` }}
              />

              {/* Hover Timestamp Preview */}
              {hoverScrub && (
                <div
                  className="absolute bottom-5 transform -translate-x-1/2 px-2 py-1 rounded bg-bg-elevated border border-border text-[10px] font-mono font-medium text-white shadow-1 pointer-events-none"
                  style={{ left: `${hoverScrub.percent}%` }}
                >
                  {formatTime(hoverScrub.time)}
                </div>
              )}
            </div>

            {/* Controls Row */}
            <div className="flex items-center justify-between gap-3 text-white">
              <div className="flex items-center gap-2 sm:gap-3">
                {/* Play / Pause */}
                <button
                  type="button"
                  onClick={togglePlay}
                  className="p-2 rounded-lg bg-surface/80 hover:bg-surface-hover backdrop-blur-md border border-white/10 text-white transition-colors"
                  aria-label={isPlaying ? "Pause" : "Play"}
                  data-testid="play-pause-btn"
                >
                  {isPlaying ? (
                    <Pause className="w-4 h-4 fill-white" />
                  ) : (
                    <Play className="w-4 h-4 fill-white" />
                  )}
                </button>

                {/* Skip Backward -10s */}
                <button
                  type="button"
                  onClick={() => seekRelative(-10)}
                  className="p-2 rounded-lg hover:bg-surface/80 text-text-muted hover:text-white transition-colors"
                  aria-label="Rewind 10 seconds"
                  title="Rewind 10s (←)"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>

                {/* Skip Forward +10s */}
                <button
                  type="button"
                  onClick={() => seekRelative(10)}
                  className="p-2 rounded-lg hover:bg-surface/80 text-text-muted hover:text-white transition-colors"
                  aria-label="Forward 10 seconds"
                  title="Forward 10s (→)"
                >
                  <RotateCw className="w-4 h-4" />
                </button>

                {/* Volume & Mute */}
                <div className="flex items-center gap-1.5 group/vol">
                  <button
                    type="button"
                    onClick={toggleMute}
                    className="p-2 rounded-lg hover:bg-surface/80 text-text-muted hover:text-white transition-colors"
                    aria-label={isMuted ? "Unmute" : "Mute"}
                    title="Mute / Unmute (M)"
                  >
                    {isMuted || volume === 0 ? (
                      <VolumeX className="w-4 h-4 text-danger" />
                    ) : (
                      <Volume2 className="w-4 h-4" />
                    )}
                  </button>

                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={isMuted ? 0 : volume}
                    onChange={(e) => changeVolume(parseFloat(e.target.value))}
                    className="w-16 sm:w-20 h-1 rounded-full accent-accent-1 bg-white/20 cursor-pointer"
                    aria-label="Volume slider"
                  />
                </div>

                {/* Time Display */}
                <div className="font-mono text-xs text-text-muted ml-2">
                  <span className="text-white font-medium">
                    {formatTime(currentTime)}
                  </span>
                  <span className="mx-1">/</span>
                  <span>{formatTime(duration)}</span>
                </div>
              </div>

              {/* Right Controls */}
              <div className="flex items-center gap-2">
                {/* Playback Speed Menu */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowSpeedMenu((prev) => !prev)}
                    className="flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-surface/80 text-xs font-mono text-text-muted hover:text-white transition-colors border border-transparent hover:border-white/10"
                    title="Playback Speed"
                    aria-label="Playback Speed"
                  >
                    <Gauge className="w-3.5 h-3.5" />
                    <span>{playbackRate}x</span>
                  </button>

                  {showSpeedMenu && (
                    <div className="absolute bottom-full right-0 mb-2 p-1 rounded-xl bg-bg-elevated/95 backdrop-blur-xl border border-border shadow-2 flex flex-col gap-0.5 min-w-[70px] z-50">
                      {[0.5, 0.75, 1, 1.25, 1.5, 2].map((rate) => (
                        <button
                          key={rate}
                          type="button"
                          onClick={() => changeSpeed(rate)}
                          className={`px-3 py-1 text-xs font-mono text-left rounded-md transition-colors ${
                            playbackRate === rate
                              ? "bg-accent-1/20 text-accent-1 font-semibold"
                              : "text-text hover:bg-surface"
                          }`}
                        >
                          {rate}x
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Subtitles toggle */}
                <button
                  type="button"
                  onClick={() =>
                    setCaptionsActive((prev) => {
                      const next = !prev;
                      showToast(next ? "Subtitles: Enabled" : "Subtitles: Off");
                      return next;
                    })
                  }
                  className={`p-2 rounded-lg transition-colors ${
                    captionsActive
                      ? "text-accent-2 bg-accent-2/10"
                      : "text-text-muted hover:text-white hover:bg-surface/80"
                  }`}
                  title="Toggle Subtitles (C)"
                  aria-label="Toggle Subtitles"
                >
                  <Subtitles className="w-4 h-4" />
                </button>

                {/* Fullscreen Button */}
                <button
                  type="button"
                  onClick={toggleFullscreen}
                  className="p-2 rounded-lg hover:bg-surface/80 text-text-muted hover:text-white transition-colors"
                  aria-label={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
                  title="Fullscreen (F)"
                >
                  {isFullscreen ? (
                    <Minimize className="w-4 h-4" />
                  ) : (
                    <Maximize className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
