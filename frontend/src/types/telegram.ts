export interface TelegramStatus {
  is_linked: boolean;
  chat_id: string | null;
  bot_username: string | null;
}

export interface TelegramLinkCode {
  code: string;
  bot_username: string | null;
  deep_link: string | null;
  expires_in_seconds: number;
}
