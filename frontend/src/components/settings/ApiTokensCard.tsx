import React, { useState } from "react";
import {
  Key,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  ShieldCheck,
  Terminal,
  Loader2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useTokens } from "@/hooks/useTokens";
import type { ApiTokenCreated } from "@/types/token";

export function ApiTokensCard() {
  const { tokens, isLoading, error, createToken, revokeToken } = useTokens();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [tokenLabel, setTokenLabel] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [revealedToken, setRevealedToken] = useState<ApiTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenLabel.trim()) return;

    try {
      setIsSubmitting(true);
      setSubmitError(null);
      const created = await createToken(tokenLabel.trim());
      setTokenLabel("");
      setIsCreateOpen(false);
      setRevealedToken(created);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create token");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = async (tokenStr: string) => {
    try {
      await navigator.clipboard.writeText(tokenStr);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const formatDate = (isoStr: string | null) => {
    if (!isoStr) return "Never";
    try {
      return new Date(isoStr).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accent-1/10 text-accent-1">
              <Key className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-text">Personal API Tokens</h2>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Authenticate CLI scripts, curl, or automated bots via Bearer tokens. Tokens are stored hashed at rest.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setIsCreateOpen(true);
            setSubmitError(null);
          }}
          data-testid="create-token-btn"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-accent-1 text-white text-xs font-medium hover:bg-accent-1/90 transition shadow-sm active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Generate Token</span>
        </button>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tokens List */}
      <div className="mt-6">
        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center text-text-muted text-xs gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-accent-1" />
            <span>Loading tokens...</span>
          </div>
        ) : tokens.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-center px-4 rounded-lg border border-dashed border-border bg-bg/50">
            <Key className="w-8 h-8 text-text-muted/40 mb-2" />
            <p className="text-xs font-medium text-text">No API tokens generated</p>
            <p className="text-[11px] text-text-muted mt-1 max-w-sm">
              Generate a personal API token to trigger downloads programmatically or query the DriveSeed API.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto" data-testid="tokens-table-container">
            <table className="w-full text-left text-xs" data-testid="tokens-table">
              <thead>
                <tr className="border-b border-border text-text-muted text-[11px] uppercase tracking-wider font-medium">
                  <th className="py-2.5 px-3">Label</th>
                  <th className="py-2.5 px-3">Prefix</th>
                  <th className="py-2.5 px-3">Created</th>
                  <th className="py-2.5 px-3">Last Used</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tokens.map((token) => (
                  <tr key={token.id} className="hover:bg-bg/40 transition-colors" data-testid={`token-row-${token.id}`}>
                    <td className="py-3 px-3 font-medium text-text">
                      {token.label}
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-text-muted">
                      <span className="px-1.5 py-0.5 rounded bg-surface border border-border">
                        {token.prefix}...
                      </span>
                    </td>
                    <td className="py-3 px-3 text-text-muted text-[11px]">
                      {formatDate(token.created_at)}
                    </td>
                    <td className="py-3 px-3 text-text-muted text-[11px]">
                      {token.last_used_at ? formatDate(token.last_used_at) : (
                        <span className="text-text-muted/60 italic">Never</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        type="button"
                        onClick={() => void revokeToken(token.id)}
                        data-testid={`revoke-token-${token.id}`}
                        aria-label={`Revoke token ${token.label}`}
                        title="Revoke Token"
                        className="p-1.5 rounded text-text-muted hover:text-red-500 hover:bg-red-500/10 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Creation Modal */}
      <AnimatePresence>
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-2xl"
              data-testid="create-token-modal"
            >
              <h3 className="text-base font-semibold text-text">Generate Personal API Token</h3>
              <p className="mt-1 text-xs text-text-muted">
                Give your token a descriptive name to remember where it is being used.
              </p>

              <form onSubmit={handleCreate} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="token-label-input" className="block text-xs font-medium text-text-muted mb-1">
                    Token Label
                  </label>
                  <input
                    id="token-label-input"
                    type="text"
                    value={tokenLabel}
                    onChange={(e) => setTokenLabel(e.target.value)}
                    placeholder="e.g. My CLI Script, Home Server"
                    data-testid="token-label-input"
                    maxLength={255}
                    required
                    autoFocus
                    className="w-full px-3 py-2 rounded-lg bg-bg border border-border text-xs text-text focus:outline-none focus:border-accent-1"
                  />
                </div>

                {submitError && (
                  <p className="text-xs text-red-500">{submitError}</p>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCreateOpen(false)}
                    className="px-3.5 py-1.5 rounded-lg border border-border text-xs text-text hover:bg-bg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !tokenLabel.trim()}
                    data-testid="submit-create-token"
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-accent-1 text-white text-xs font-medium hover:bg-accent-1/90 transition disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Plus className="w-3.5 h-3.5" />
                    )}
                    <span>Create</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* One-Time Token Reveal Modal */}
      <AnimatePresence>
        {revealedToken && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg rounded-xl border border-border bg-surface p-6 shadow-2xl"
              data-testid="revealed-token-modal"
            >
              <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                <ShieldCheck className="w-5 h-5" />
                <span>Token Created: {revealedToken.label}</span>
              </div>

              {/* Warning Notice */}
              <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-500 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Copy your token now!</p>
                  <p className="text-[11px] mt-0.5 opacity-90">
                    For security reasons, this token will never be displayed again. If you lose it, you will need to revoke it and generate a new one.
                  </p>
                </div>
              </div>

              {/* Token Display Box */}
              <div className="mt-4">
                <label className="block text-[11px] font-medium text-text-muted mb-1">
                  Personal Access Token
                </label>
                <div className="flex items-center gap-2">
                  <div
                    data-testid="revealed-token-value"
                    className="flex-1 font-mono text-xs px-3 py-2.5 rounded-lg bg-bg border border-border text-accent-1 select-all break-all"
                  >
                    {revealedToken.token}
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleCopy(revealedToken.token)}
                    data-testid="copy-token-btn"
                    className="p-2.5 rounded-lg bg-accent-1 text-white hover:bg-accent-1/90 transition shadow-sm"
                    title="Copy token to clipboard"
                  >
                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Quick cURL snippet */}
              <div className="mt-4 p-3 rounded-lg bg-bg border border-border text-xs">
                <div className="flex items-center gap-1.5 text-text-muted text-[11px] mb-1 font-mono">
                  <Terminal className="w-3.5 h-3.5" />
                  <span>Example usage:</span>
                </div>
                <code className="block font-mono text-[11px] text-text-muted break-all">
                  curl -H &quot;Authorization: Bearer {revealedToken.token}&quot; http://localhost:8000/api/tasks
                </code>
              </div>

              <div className="mt-5 flex justify-end">
                <button
                  type="button"
                  onClick={() => setRevealedToken(null)}
                  data-testid="close-revealed-modal"
                  className="px-4 py-2 rounded-lg bg-accent-1 text-white text-xs font-medium hover:bg-accent-1/90 transition shadow-sm"
                >
                  I have saved this token
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
