/**
 * TypeScript types for media playback state and resume tracking.
 */

export interface PlaybackInfo {
  file_id: string;
  position_seconds: number;
  updated_at?: string | null;
}

export interface PlaybackUpdateRequest {
  position_seconds: number;
}
