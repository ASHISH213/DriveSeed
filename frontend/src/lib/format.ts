/**
 * Formatting utilities for file sizes, network speeds, and durations.
 */

export function formatBytes(bytes?: number): string {
  if (bytes === undefined || bytes === null || isNaN(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let val = bytes;
  let idx = 0;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export function formatSpeed(bps?: number): string {
  if (!bps || isNaN(bps) || bps <= 0) return "0 B/s";
  return `${formatBytes(bps)}/s`;
}

export function formatEta(seconds?: number | null): string {
  if (seconds === undefined || seconds === null || isNaN(seconds) || seconds <= 0) return "";
  if (seconds < 60) return `~${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `~${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `~${hours}h ${remMins}m`;
}

export function formatTime(seconds?: number | null): string {
  if (!seconds || isNaN(seconds) || seconds <= 0) return "0:00";
  const total = Math.floor(seconds);
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  const paddedSecs = secs.toString().padStart(2, "0");
  if (hrs > 0) {
    const paddedMins = mins.toString().padStart(2, "0");
    return `${hrs}:${paddedMins}:${paddedSecs}`;
  }
  return `${mins}:${paddedSecs}`;
}
