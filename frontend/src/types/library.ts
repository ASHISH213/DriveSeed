/**
 * TypeScript types for DriveSeed Google Drive library browsing and file operations.
 */

export interface LibraryItem {
  id: string;
  name: string;
  parent_id: string;
  mime_type: string;
  is_folder: boolean;
  size_bytes: number;
  md5?: string | null;
}

export interface BreadcrumbItem {
  id: string;
  name: string;
}

export interface FileListResponse {
  current_folder_id: string;
  breadcrumbs: BreadcrumbItem[];
  files: LibraryItem[];
}

export type ViewMode = "grid" | "list";
