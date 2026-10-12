import React, { useState } from "react";
import {
  Webhook,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Send,
  Loader2,
  CheckCircle2,
  XCircle,
  Code,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useWebhooks } from "@/hooks/useWebhooks";
import type { WebhookTestResult } from "@/types/webhook";

export function WebhooksCard() {
  const {
    webhooks,
    isLoading,
    error,
    createWebhook,
    deleteWebhook,
    testWebhook,
  } = useWebhooks();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [events, setEvents] = useState<string[]>([
    "task.completed",
    "task.failed",
  ]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, WebhookTestResult>
  >({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    try {
      setIsSubmitting(true);
      setSubmitError(null);
      await createWebhook({
        url: url.trim(),
        secret: secret.trim() || undefined,
        events,
      });
      setUrl("");
      setSecret("");
      setEvents(["task.completed", "task.failed"]);
      setIsModalOpen(false);
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to register webhook"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopySecret = async (endpointId: string, secretStr: string) => {
    try {
      await navigator.clipboard.writeText(secretStr);
      setCopiedId(endpointId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Fallback
    }
  };

  const handleTestPing = async (endpointId: string) => {
    setTestingId(endpointId);
    try {
      const res = await testWebhook(endpointId);
      setTestResults((prev) => ({ ...prev, [endpointId]: res }));
    } catch (err: unknown) {
      setTestResults((prev) => ({
        ...prev,
        [endpointId]: {
          success: false,
          status_code: null,
          message: err instanceof Error ? err.message : "Test failed",
        },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const toggleEvent = (eventName: string) => {
    setEvents((prev) =>
      prev.includes(eventName)
        ? prev.filter((e) => e !== eventName)
        : [...prev, eventName]
    );
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accent-2/10 text-accent-2">
              <Webhook className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-text">Task Webhooks</h2>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Deliver signed HMAC-SHA256 payloads to external endpoints when downloads complete or fail.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setIsModalOpen(true);
            setSubmitError(null);
          }}
          data-testid="add-webhook-btn"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-accent-2 text-white text-xs font-medium hover:bg-accent-2/90 transition shadow-sm active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Add Webhook</span>
        </button>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Webhooks List */}
      <div className="mt-6">
        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center text-text-muted text-xs gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-accent-2" />
            <span>Loading webhooks...</span>
          </div>
        ) : webhooks.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-center px-4 rounded-lg border border-dashed border-border bg-bg/50">
            <Webhook className="w-8 h-8 text-text-muted/40 mb-2" />
            <p className="text-xs font-medium text-text">No webhooks registered</p>
            <p className="text-[11px] text-text-muted mt-1 max-w-sm">
              Register an HTTP POST endpoint to automate post-processing, trigger Discord/Slack bots, or notify home servers.
            </p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="webhooks-list">
            {webhooks.map((wh) => {
              const testResult = testResults[wh.id];
              return (
                <div
                  key={wh.id}
                  data-testid={`webhook-item-${wh.id}`}
                  className="p-4 rounded-xl border border-border bg-bg/40 hover:bg-bg/60 transition-colors flex flex-col gap-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="font-mono text-xs text-text font-medium truncate max-w-md">
                        {wh.url}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider ${
                          wh.is_active
                            ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                            : "bg-text-muted/10 text-text-muted"
                        }`}
                      >
                        {wh.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => void handleTestPing(wh.id)}
                        disabled={testingId === wh.id}
                        data-testid={`test-webhook-${wh.id}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border text-text hover:bg-surface text-xs transition disabled:opacity-50"
                        title="Send a test ping event"
                      >
                        {testingId === wh.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-2" />
                        ) : (
                          <Send className="w-3.5 h-3.5 text-accent-2" />
                        )}
                        <span>Test Ping</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => void deleteWebhook(wh.id)}
                        data-testid={`delete-webhook-${wh.id}`}
                        className="p-1.5 rounded-lg text-text-muted hover:text-red-500 hover:bg-red-500/10 transition"
                        title="Delete Webhook"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Subscribed events & signing secret */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted pt-1 border-t border-border/50">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-text-muted">Events:</span>
                      {wh.events.map((ev) => (
                        <span
                          key={ev}
                          className="px-1.5 py-0.5 rounded bg-surface border border-border text-[10px] font-mono text-accent-1"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <span className="text-[11px] text-text-muted font-sans">Secret:</span>
                      <span className="px-1.5 py-0.5 rounded bg-surface border border-border text-text-muted">
                        {wh.secret.substring(0, 10)}...
                      </span>
                      <button
                        type="button"
                        onClick={() => void handleCopySecret(wh.id, wh.secret)}
                        data-testid={`copy-secret-${wh.id}`}
                        className="p-1 rounded hover:bg-surface text-text-muted hover:text-text transition"
                        title="Copy webhook secret"
                      >
                        {copiedId === wh.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Ping test feedback banner */}
                  {testResult && (
                    <div
                      data-testid={`test-result-${wh.id}`}
                      className={`p-2.5 rounded-lg text-xs flex items-center justify-between border ${
                        testResult.success
                          ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                          : "bg-red-500/10 border-red-500/20 text-red-500"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {testResult.success ? (
                          <CheckCircle2 className="w-4 h-4 shrink-0" />
                        ) : (
                          <XCircle className="w-4 h-4 shrink-0" />
                        )}
                        <span>
                          {testResult.success
                            ? `Ping delivered successfully (HTTP ${testResult.status_code || 200})`
                            : `Delivery failed: ${testResult.message}`}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          setTestResults((prev) => {
                            const next = { ...prev };
                            delete next[wh.id];
                            return next;
                          })
                        }
                        className="text-[11px] underline opacity-80 hover:opacity-100"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Signature Verification Note */}
      <div className="mt-6 p-3 rounded-lg bg-bg border border-border text-[11px] text-text-muted flex items-start gap-2">
        <Code className="w-4 h-4 text-accent-1 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-text">HMAC Signature Header: </span>
          Incoming requests contain <code className="font-mono text-accent-1">X-DriveSeed-Signature: sha256=&lt;hex&gt;</code>.
          Compute the HMAC-SHA256 of the raw body using your secret to verify authenticity.
        </div>
      </div>

      {/* Register Webhook Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-2xl"
              data-testid="create-webhook-modal"
            >
              <h3 className="text-base font-semibold text-text">Register Webhook</h3>
              <p className="mt-1 text-xs text-text-muted">
                Enter your receiver URL to receive task lifecycle events.
              </p>

              <form onSubmit={handleCreate} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="webhook-url-input" className="block text-xs font-medium text-text-muted mb-1">
                    Endpoint URL
                  </label>
                  <input
                    id="webhook-url-input"
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com/api/driveseed-hook"
                    data-testid="webhook-url-input"
                    required
                    autoFocus
                    className="w-full px-3 py-2 rounded-lg bg-bg border border-border text-xs text-text focus:outline-none focus:border-accent-2"
                  />
                </div>

                <div>
                  <label htmlFor="webhook-secret-input" className="block text-xs font-medium text-text-muted mb-1">
                    Signing Secret (Optional)
                  </label>
                  <input
                    id="webhook-secret-input"
                    type="text"
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    placeholder="Leave empty to auto-generate (whsec_...)"
                    data-testid="webhook-secret-input"
                    className="w-full px-3 py-2 rounded-lg bg-bg border border-border text-xs text-text focus:outline-none focus:border-accent-2"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-muted mb-1.5">
                    Subscribed Events
                  </label>
                  <div className="space-y-2">
                    {["task.completed", "task.failed"].map((evName) => (
                      <label key={evName} className="flex items-center gap-2 text-xs text-text cursor-pointer">
                        <input
                          type="checkbox"
                          checked={events.includes(evName)}
                          onChange={() => toggleEvent(evName)}
                          className="rounded border-border text-accent-2 focus:ring-accent-2"
                        />
                        <span className="font-mono">{evName}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {submitError && (
                  <p className="text-xs text-red-500">{submitError}</p>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-3.5 py-1.5 rounded-lg border border-border text-xs text-text hover:bg-bg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !url.trim() || events.length === 0}
                    data-testid="submit-create-webhook"
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-accent-2 text-white text-xs font-medium hover:bg-accent-2/90 transition disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Plus className="w-3.5 h-3.5" />
                    )}
                    <span>Register</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
