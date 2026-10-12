/**
 * TypeScript types for Google Drive storage quota metrics.
 */

export interface StorageQuota {
  used_bytes: number;
  total_bytes: number;
  free_bytes: number;
  percent_used: number;
}
