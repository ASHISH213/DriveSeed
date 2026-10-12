import { useState } from "react";
import {
  Send,
  Link2,
  Unlink,
  Copy,
  Check,
  AlertTriangle,
  Loader2,
  ExternalLink,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useTelegram } from "@/hooks/useTelegram";
import type { TelegramLinkCode } from "@/types/telegram";

export function TelegramCard() {
  const { status, isLoading, error, generateLinkCode, unlinkTelegram, fetchStatus } =
    useTelegram();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [linkData, setLinkData] = useState<TelegramLinkCode | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isUnlinking, setIsUnlinking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleStartConnect = async () => {
    setIsModalOpen(true);
    setIsGenerating(true);
    setActionError(null);
    setLinkData(null);
    try {
      const data = await generateLinkCode();
      setLinkData(data);
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to generate link code"
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyCode = async () => {
    if (!linkData?.code) return;
    try {
      await navigator.clipboard.writeText(linkData.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleUnlink = async () => {
    if (!confirm("Are you sure you want to disconnect your Telegram account?")) return;
    setIsUnlinking(true);
    setActionError(null);
    try {
      await unlinkTelegram();
      await fetchStatus();
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to disconnect Telegram"
      );
    } finally {
      setIsUnlinking(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-500">
              <Send className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-text">Telegram Bot</h2>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Start downloads, monitor active tasks, and receive instant completion alerts directly in Telegram.
          </p>
        </div>

        <div>
          {status?.is_linked ? (
            <button
              type="button"
              onClick={() => void handleUnlink()}
              disabled={isUnlinking}
              data-testid="unlink-telegram-btn"
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-red-500/30 text-red-500 hover:bg-red-500/10 text-xs font-medium transition active:scale-95 disabled:opacity-50"
            >
              {isUnlinking ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Unlink className="w-4 h-4" />
              )}
              <span>Disconnect</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handleStartConnect()}
              disabled={isLoading}
              data-testid="connect-telegram-btn"
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-sky-500 text-white text-xs font-medium hover:bg-sky-600 transition shadow-sm active:scale-95 disabled:opacity-50"
            >
              <Link2 className="w-4 h-4" />
              <span>Connect Telegram</span>
            </button>
          )}
        </div>
      </div>

      {/* Global / Action Error Banner */}
      {(error || actionError) && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{actionError || error}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="mt-6">
        {isLoading ? (
          <div className="py-8 flex flex-col items-center justify-center text-text-muted text-xs gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-sky-500" />
            <span>Loading Telegram status...</span>
          </div>
        ) : status?.is_linked ? (
          <div
            data-testid="telegram-linked-status"
            className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-500">
                <Check className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-text">
                    Telegram Account Connected
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-500 uppercase tracking-wider">
                    Active
                  </span>
                </div>
                <p className="text-[11px] text-text-muted font-mono mt-0.5">
                  Chat ID: {status.chat_id}
                </p>
              </div>
            </div>

            <div className="text-[11px] text-text-muted sm:text-right">
              Push notifications enabled for task completions and errors.
            </div>
          </div>
        ) : (
          <div
            data-testid="telegram-unlinked-status"
            className="p-6 rounded-xl border border-dashed border-border bg-bg/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-lg bg-surface border border-border text-text-muted shrink-0">
                <MessageSquare className="w-5 h-5 text-sky-500" />
              </div>
              <div>
                <p className="text-xs font-medium text-text">Not Connected</p>
                <p className="text-[11px] text-text-muted mt-1 max-w-md">
                  Connect your Telegram account to send magnet links or URLs on the go and receive notifications when files are saved to Google Drive.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Command Cheat Sheet */}
        <div className="mt-6 pt-5 border-t border-border">
          <h3 className="text-xs font-semibold text-text flex items-center gap-1.5 mb-3">
            <Sparkles className="w-3.5 h-3.5 text-sky-500" />
            <span>Supported Bot Commands</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
            <div className="p-3 rounded-lg border border-border bg-bg/50">
              <code className="text-sky-500 font-mono font-medium">/add &lt;magnet|url&gt;</code>
              <p className="text-[11px] text-text-muted mt-1">
                Queue and start a torrent or direct download into your Google Drive.
              </p>
            </div>
            <div className="p-3 rounded-lg border border-border bg-bg/50">
              <code className="text-sky-500 font-mono font-medium">/status</code>
              <p className="text-[11px] text-text-muted mt-1">
                View real-time progress and speeds of all active tasks.
              </p>
            </div>
            <div className="p-3 rounded-lg border border-border bg-bg/50">
              <code className="text-sky-500 font-mono font-medium">/library</code>
              <p className="text-[11px] text-text-muted mt-1">
                Browse recent files saved in your Google Drive library.
              </p>
            </div>
            <div className="p-3 rounded-lg border border-border bg-bg/50">
              <code className="text-sky-500 font-mono font-medium">/help</code>
              <p className="text-[11px] text-text-muted mt-1">
                Display the list of available commands and instructions.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Connect Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            data-testid="telegram-modal-backdrop"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl flex flex-col gap-5"
            >
              <div>
                <h3 className="text-base font-semibold text-text">
                  Connect Telegram Account
                </h3>
                <p className="text-xs text-text-muted mt-1">
                  Send your temporary link code to the DriveSeed bot to authenticate this chat.
                </p>
              </div>

              {isGenerating ? (
                <div className="py-10 flex flex-col items-center justify-center text-xs text-text-muted gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-sky-500" />
                  <span>Generating link code...</span>
                </div>
              ) : linkData ? (
                <div className="space-y-4">
                  {/* Code Display */}
                  <div className="p-4 rounded-xl border border-sky-500/20 bg-sky-500/5 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">
                        Your Link Code (Expires in 10m)
                      </span>
                      <div
                        data-testid="telegram-link-code-display"
                        className="font-mono text-2xl font-bold tracking-widest text-sky-500 mt-1"
                      >
                        {linkData.code}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => void handleCopyCode()}
                      data-testid="copy-code-btn"
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-border text-xs font-medium text-text hover:bg-bg transition"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-500" />
                          <span className="text-emerald-500">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5 text-text-muted" />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Steps */}
                  <div className="p-3 rounded-lg border border-border bg-bg/50 space-y-2 text-xs text-text-muted">
                    <div className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-surface border border-border flex items-center justify-center font-bold text-[10px] text-text shrink-0">
                        1
                      </span>
                      <span>
                        Open the Telegram bot:{" "}
                        <strong className="text-text">
                          @{linkData.bot_username || "DriveSeedBot"}
                        </strong>
                      </span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="w-5 h-5 rounded-full bg-surface border border-border flex items-center justify-center font-bold text-[10px] text-text shrink-0">
                        2
                      </span>
                      <span>
                        Send the message:{" "}
                        <code className="text-sky-500 font-mono font-medium">
                          /start {linkData.code}
                        </code>
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col sm:flex-row items-center gap-2 pt-2">
                    {linkData.deep_link && (
                      <a
                        href={linkData.deep_link}
                        target="_blank"
                        rel="noreferrer"
                        data-testid="open-telegram-btn"
                        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-sky-500 text-white text-xs font-medium hover:bg-sky-600 transition shadow-sm text-center"
                      >
                        <span>Open in Telegram</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        setIsModalOpen(false);
                        void fetchStatus();
                      }}
                      className="w-full sm:w-auto px-4 py-2 rounded-lg border border-border text-xs text-text-muted hover:text-text hover:bg-bg transition"
                    >
                      Done
                    </button>
                  </div>
                </div>
              ) : null}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
