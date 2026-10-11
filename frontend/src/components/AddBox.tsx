import React, { useState } from "react";
import { Magnet, Link as LinkIcon, Plus, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";

interface AddBoxProps {
  onAdd: (sourceUri: string, name?: string) => Promise<unknown>;
  disabled?: boolean;
}

export const AddBox: React.FC<AddBoxProps> = ({ onAdd, disabled = false }) => {
  const [uri, setUri] = useState("");
  const [customName, setCustomName] = useState("");
  const [showNameInput, setShowNameInput] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = uri.trim();
  const isMagnet = trimmed.startsWith("magnet:");
  const isHttp = trimmed.startsWith("http://") || trimmed.startsWith("https://");
  const isValid = isMagnet || isHttp;

  const { slideFade } = useMotionPreset();

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!trimmed || isSubmitting || disabled) return;

    if (!isValid) {
      setError("Please enter a valid magnet link or HTTP/HTTPS download URL");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await onAdd(trimmed, customName.trim() || undefined);
      setUri("");
      setCustomName("");
      setShowNameInput(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add download");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form
        onSubmit={handleSubmit}
        className="relative flex flex-col gap-3 p-2 sm:p-3 rounded-xl bg-bg-elevated border border-border transition-all duration-200 focus-within:shadow-glow focus-within:border-accent-1 shadow-1"
      >
        <div className="flex items-center gap-3 px-3 py-1.5">
          {/* Source Type Icon Indicator */}
          <div className="w-8 h-8 rounded-lg bg-surface border border-border flex items-center justify-center flex-shrink-0 text-text-muted">
            {isMagnet ? (
              <Magnet className="w-4 h-4 text-accent-1 animate-pulse" />
            ) : isHttp ? (
              <LinkIcon className="w-4 h-4 text-accent-2" />
            ) : (
              <Sparkles className="w-4 h-4 text-text-muted" />
            )}
          </div>

          {/* Main URI Input */}
          <input
            type="text"
            value={uri}
            onChange={(e) => {
              setUri(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Paste magnet link or direct download URL (http / https)..."
            disabled={isSubmitting || disabled}
            className="flex-1 bg-transparent text-sm sm:text-base text-text placeholder-text-muted focus:outline-none"
            aria-label="Download source URI"
          />

          {/* Action Button */}
          <button
            type="submit"
            disabled={!isValid || isSubmitting || disabled}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-grad text-white text-sm font-medium shadow-1 hover:opacity-95 active:scale-[0.98] transition-all disabled:opacity-40 disabled:pointer-events-none flex-shrink-0"
            aria-label="Add download"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <Plus className="w-4 h-4" />
                <span className="hidden sm:inline">Add Download</span>
              </>
            )}
          </button>
        </div>

        {/* Optional Custom Name Toggle & Field */}
        <div className="flex items-center justify-between px-3 pt-1 border-t border-border/50 text-xs text-text-muted">
          <button
            type="button"
            onClick={() => setShowNameInput((prev) => !prev)}
            className="hover:text-text transition-colors flex items-center gap-1"
          >
            <span>{showNameInput ? "− Remove custom name" : "+ Optional custom filename"}</span>
          </button>

          <span className="font-mono text-[11px] opacity-70">
            {isMagnet ? "Magnet link detected" : isHttp ? "Direct URL detected" : "Ready"}
          </span>
        </div>

        {/* Collapsible custom filename input */}
        <AnimatePresence>
          {showNameInput && (
            <motion.div {...slideFade} className="px-3 pb-1">
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="Custom file or folder name (optional)..."
                disabled={isSubmitting || disabled}
                className="w-full px-3 py-1.5 text-xs rounded-md bg-surface border border-border text-text placeholder-text-muted focus:outline-none focus:border-accent-1"
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Inline Error Message */}
        <AnimatePresence>
          {error && (
            <motion.div
              {...slideFade}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs"
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>
      </form>
    </div>
  );
};
