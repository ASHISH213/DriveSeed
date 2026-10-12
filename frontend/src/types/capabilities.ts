export interface FeatureFlags {
  torrent: boolean;
  direct_download: boolean;
  streaming: boolean;
  transcoding: boolean;
  rss: boolean;
  telegram: boolean;
  webhooks: boolean;
  multi_user: boolean;
}

export interface RuntimeLimits {
  max_active_tasks: number;
}

export interface CapabilitiesResponse {
  profile: 'server' | 'colab' | string;
  storage_backend: 'drive_api' | 'mounted' | string;
  features: FeatureFlags;
  limits: RuntimeLimits;
}
