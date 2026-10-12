export interface ApiToken {
  id: string;
  prefix: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
}

export interface ApiTokenCreated extends ApiToken {
  token: string;
}
