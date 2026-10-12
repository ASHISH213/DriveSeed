/**
 * TypeScript types for DriveSeed tasks, files, and live events.
 */

export type TaskState =
  | "queued"
  | "fetching_metadata"
  | "awaiting_selection"
  | "downloading"
  | "uploading"
  | "completed"
  | "paused"
  | "failed"
  | "cancelled";

export interface TaskStartRequest {
  selected_file_ids?: string[];
  destination_folder_id?: string | null;
}

export interface TaskFile {
  id: string;
  path: string;
  size_bytes: number;
  selected: boolean;
  state: string;
  drive_file_id: string | null;
}

export interface Task {
  id: string;
  user_id: string;
  source_type: "url" | "magnet";
  source_uri: string;
  info_hash: string | null;
  name: string;
  state: TaskState;
  progress: number;
  size_bytes: number | null;
  speed_bps?: number;
  downloaded_bytes?: number;
  total_bytes?: number;
  eta_seconds?: number | null;
  error: string | null;
  files: TaskFile[];
  created_at: string;
  completed_at: string | null;
}

export interface TaskEvent {
  task_id: string;
  user_id: string;
  state: TaskState;
  name?: string | null;
  progress: number;
  speed_bps: number;
  downloaded_bytes: number;
  total_bytes: number;
  error?: string | null;
  timestamp: number;
}

export interface TaskCreateRequest {
  source_uri: string;
  name?: string;
}
