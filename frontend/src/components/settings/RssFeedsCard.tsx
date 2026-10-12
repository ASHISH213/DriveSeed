import React, { useState } from "react";
import {
  Rss,
  Plus,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  XCircle,
  Filter,
  Eye,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useRss } from "@/hooks/useRss";
import type { RssPreviewResult, RssSyncResult } from "@/types/rss";

export function RssFeedsCard() {
  const {
    subscriptions,
    isLoading,
    error,
    createSubscription,
    deleteSubscription,
    previewFeed,
    syncSubscription,
  } = useRss();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [filterRegex, setFilterRegex] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Preview state
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState<RssPreviewResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Sync state
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncResults, setSyncResults] = useState<Record<string, RssSyncResult>>({});

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !url.trim()) return;

    try {
      setIsSubmitting(true);
      setSubmitError(null);
      await createSubscription({
        name: name.trim(),
        url: url.trim(),
        filter_regex: filterRegex.trim() || undefined,
      });
      setName("");
      setUrl("");
      setFilterRegex("");
      setPreviewResult(null);
      setPreviewError(null);
      setIsModalOpen(false);
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to create RSS subscription"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePreview = async () => {
    if (!url.trim()) {
      setPreviewError("Please enter a feed URL to preview");
      return;
    }

    setIsPreviewing(true);
    setPreviewError(null);
    setPreviewResult(null);

    try {
      const res = await previewFeed(url.trim(), filterRegex.trim() || undefined);
      setPreviewResult(res);
    } catch (err: unknown) {
      setPreviewError(
        err instanceof Error ? err.message : "Failed to preview feed"
      );
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleSyncNow = async (id: string) => {
    setSyncingId(id);
    try {
      const res = await syncSubscription(id);
      setSyncResults((prev) => ({ ...prev, [id]: res }));
    } catch {
      setSyncResults((prev) => ({
        ...prev,
        [id]: {
          subscription_id: id,
          items_checked: 0,
          tasks_created: 0,
          created_task_ids: [],
        },
      }));
    } finally {
      setSyncingId(null);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-orange-500/10 text-orange-500">
              <Rss className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-text">RSS Feeds</h2>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Automatically monitor RSS 2.0 and Atom feeds to start downloads matching your regex filters.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setIsModalOpen(true);
            setSubmitError(null);
            setPreviewResult(null);
            setPreviewError(null);
          }}
          data-testid="add-rss-btn"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 transition shadow-sm active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>Add Feed</span>
        </button>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Feeds List */}
      <div className="mt-6">
        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center text-text-muted text-xs gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
            <span>Loading RSS feeds...</span>
          </div>
        ) : subscriptions.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-center px-4 rounded-lg border border-dashed border-border bg-bg/50">
            <Rss className="w-8 h-8 text-text-muted/40 mb-2" />
            <p className="text-xs font-medium text-text">No RSS feeds configured</p>
            <p className="text-[11px] text-text-muted mt-1 max-w-sm">
              Add your favourite podcast, Linux distribution, or torrent feeds with optional regex matching for automated fetching.
            </p>
          </div>
        ) : (
          <div className="space-y-3" data-testid="rss-list">
            {subscriptions.map((sub) => {
              const syncResult = syncResults[sub.id];
              return (
                <div
                  key={sub.id}
                  data-testid={`rss-item-${sub.id}`}
                  className="p-4 rounded-xl border border-border bg-bg/40 hover:bg-bg/60 transition-colors flex flex-col gap-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-text truncate">
                          {sub.name}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider ${
                            sub.is_active
                              ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                              : "bg-text-muted/10 text-text-muted"
                          }`}
                        >
                          {sub.is_active ? "Active" : "Paused"}
                        </span>
                      </div>
                      <p className="font-mono text-[11px] text-text-muted truncate mt-0.5">
                        {sub.url}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => void handleSyncNow(sub.id)}
                        disabled={syncingId === sub.id}
                        data-testid={`sync-rss-${sub.id}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border text-text hover:bg-surface text-xs transition disabled:opacity-50"
                        title="Check feed for new downloads immediately"
                      >
                        {syncingId === sub.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-500" />
                        ) : (
                          <RefreshCw className="w-3.5 h-3.5 text-orange-500" />
                        )}
                        <span>Sync Now</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => void deleteSubscription(sub.id)}
                        data-testid={`delete-rss-${sub.id}`}
                        className="p-1.5 rounded-lg border border-border text-text-muted hover:text-red-500 hover:border-red-500/30 hover:bg-red-500/10 transition"
                        title="Delete RSS subscription"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Metadata and Regex info */}
                  <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border/50 text-[11px] text-text-muted">
                    {sub.filter_regex ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface border border-border font-mono text-[10px] text-accent">
                        <Filter className="w-3 h-3" />
                        <span>/{sub.filter_regex}/</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-text-muted/70">
                        Matches all items
                      </span>
                    )}

                    {sub.last_checked_at ? (
                      <span>
                        Last synced: {new Date(sub.last_checked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    ) : (
                      <span>Not synced yet</span>
                    )}

                    {sub.last_item_title && (
                      <span className="truncate max-w-xs text-text/80">
                        Latest: {sub.last_item_title}
                      </span>
                    )}
                  </div>

                  {/* Recent Sync Result Banner */}
                  {syncResult && (
                    <div
                      data-testid={`sync-result-${sub.id}`}
                      className="px-3 py-2 rounded-lg bg-surface border border-border text-[11px] flex items-center justify-between"
                    >
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        <span className="text-text font-medium">
                          Checked {syncResult.items_checked} item{syncResult.items_checked === 1 ? "" : "s"}.
                        </span>
                        <span className="text-emerald-500 font-semibold">
                          Created {syncResult.tasks_created} new task{syncResult.tasks_created === 1 ? "" : "s"}.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Feed Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            data-testid="rss-modal-backdrop"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-xl flex flex-col gap-5 max-h-[90vh] overflow-y-auto"
            >
              <div>
                <h3 className="text-base font-semibold text-text">
                  Add RSS / Atom Feed
                </h3>
                <p className="text-xs text-text-muted mt-1">
                  Specify a feed URL and an optional regex filter to download only items matching desired keywords.
                </p>
              </div>

              {submitError && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

              <form onSubmit={(e) => void handleCreate(e)} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Feed Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Ubuntu Daily ISOs"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-xs focus:outline-none focus:ring-1 focus:ring-orange-500"
                    data-testid="rss-name-input"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Feed URL *
                  </label>
                  <input
                    type="url"
                    required
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.org/feed.xml"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text text-xs focus:outline-none focus:ring-1 focus:ring-orange-500"
                    data-testid="rss-url-input"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium text-text">
                      Title Regex Filter (optional)
                    </label>
                    <span className="text-[10px] text-text-muted">
                      Case-insensitive: <code className="font-mono text-orange-500">(?i)pattern</code>
                    </span>
                  </div>
                  <input
                    type="text"
                    value={filterRegex}
                    onChange={(e) => setFilterRegex(e.target.value)}
                    placeholder="e.g. (?i)ubuntu.*amd64"
                    className="w-full px-3 py-2 rounded-lg border border-border bg-bg text-text font-mono text-xs focus:outline-none focus:ring-1 focus:ring-orange-500"
                    data-testid="rss-regex-input"
                  />
                  <p className="mt-1 text-[11px] text-text-muted">
                    Leave blank to match all enclosure links and magnet URLs found in the feed.
                  </p>
                </div>

                {/* Preview Button */}
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() => void handlePreview()}
                    disabled={isPreviewing || !url.trim()}
                    data-testid="rss-preview-btn"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs text-text hover:bg-bg transition disabled:opacity-50"
                  >
                    {isPreviewing ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-500" />
                    ) : (
                      <Eye className="w-3.5 h-3.5 text-orange-500" />
                    )}
                    <span>Preview Feed & Filter</span>
                  </button>
                </div>

                {/* Preview Results Box */}
                {previewError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{previewError}</span>
                  </div>
                )}

                {previewResult && (
                  <div
                    data-testid="rss-preview-result"
                    className="p-3 rounded-lg border border-border bg-bg/60 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between text-text-muted text-[11px] pb-1 border-b border-border/50">
                      <span>Feed: <strong className="text-text">{previewResult.feed_title || "Untitled Feed"}</strong></span>
                      <span>
                        Total: {previewResult.total_items} | Matches:{" "}
                        <strong className="text-orange-500">
                          {previewResult.matching_items.filter((i) => i.is_match).length}
                        </strong>
                      </span>
                    </div>

                    <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                      {previewResult.matching_items.map((item, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2 py-1 text-[11px]"
                        >
                          {item.is_match ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="w-3.5 h-3.5 text-text-muted/40 shrink-0 mt-0.5" />
                          )}
                          <div className="min-w-0">
                            <p
                              className={`truncate font-medium ${
                                item.is_match ? "text-text" : "text-text-muted"
                              }`}
                            >
                              {item.title}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Modal Actions */}
                <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                  <button
                    type="button"
                    onClick={() => {
                      setIsModalOpen(false);
                      setPreviewResult(null);
                    }}
                    className="px-3.5 py-2 rounded-lg border border-border text-xs text-text-muted hover:text-text hover:bg-bg transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !name.trim() || !url.trim()}
                    data-testid="rss-submit-btn"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 transition shadow-sm disabled:opacity-50"
                  >
                    {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    <span>Save Feed</span>
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
