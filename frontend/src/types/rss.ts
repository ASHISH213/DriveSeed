export interface RssSubscription {
  id: string;
  name: string;
  url: string;
  filter_regex: string | null;
  is_active: boolean;
  last_checked_at: string | null;
  last_item_title: string | null;
  created_at: string;
}

export interface RssCreateRequest {
  name: string;
  url: string;
  filter_regex?: string;
}

export interface RssItemPreview {
  title: string;
  link: string;
  is_match: boolean;
}

export interface RssPreviewResult {
  feed_title: string | null;
  total_items: number;
  matching_items: RssItemPreview[];
}

export interface RssSyncResult {
  subscription_id: string;
  items_checked: number;
  tasks_created: number;
  created_task_ids: string[];
}
