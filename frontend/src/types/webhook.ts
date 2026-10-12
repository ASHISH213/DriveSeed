export interface WebhookEndpoint {
  id: string;
  url: string;
  secret: string;
  events: string[];
  is_active: boolean;
  created_at: string;
}

export interface WebhookCreateRequest {
  url: string;
  secret?: string;
  events?: string[];
}

export interface WebhookTestResult {
  success: boolean;
  status_code: number | null;
  message: string;
}
