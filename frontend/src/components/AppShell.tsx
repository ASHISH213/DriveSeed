import React, { useEffect, useState } from "react";
import { Moon, Sun, HardDrive, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";

export type Theme = "dark" | "light";

interface AppShellProps {
  children?: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("driveseed-theme") as Theme | null;
      if (saved === "light" || saved === "dark") return saved;
      return "dark";
    }
    return "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "light") {
      root.setAttribute("data-theme", "light");
    } else {
      root.removeAttribute("data-theme");
    }
    localStorage.setItem("driveseed-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const { slideFade } = useMotionPreset();

  return (
    <div className="min-h-screen flex flex-col bg-bg text-text transition-colors duration-200">
      {/* Glass Header */}
      <header className="sticky top-0 z-50 glass-header px-4 sm:px-8 py-3 transition-colors duration-200">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-md bg-accent-grad flex items-center justify-center shadow-glow">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-semibold text-lg tracking-tight bg-gradient-to-r from-accent-1 to-accent-2 bg-clip-text text-transparent">
                DriveSeed
              </span>
              <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-xs font-mono rounded bg-surface border border-border text-text-muted">
                v0.1.0
              </span>
            </div>
          </div>

          {/* Right Controls: Storage Ring Indicator & Theme Toggle */}
          <div className="flex items-center gap-4">
            {/* Storage Ring Stub */}
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface border border-border hover:bg-surface-hover transition-colors"
              title="Google Drive Storage (Connecting...)"
              data-testid="storage-indicator"
            >
              <div className="relative w-5 h-5 flex items-center justify-center">
                <svg className="w-5 h-5 transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-border"
                    strokeWidth="4"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-success"
                    strokeDasharray="25, 100"
                    strokeWidth="4"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <HardDrive className="w-2.5 h-2.5 text-text-muted absolute" />
              </div>
              <span className="text-xs font-mono tabular-nums text-text-muted hidden sm:inline">
                Drive Ready
              </span>
            </div>

            {/* Dark/Light Theme Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle theme"
              data-testid="theme-toggle"
              className="p-2 rounded-md bg-surface border border-border hover:bg-surface-hover hover:shadow-glow focus:outline-none focus:ring-2 focus:ring-accent-1 text-text transition-all duration-150"
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4 text-warning" />
              ) : (
                <Moon className="w-4 h-4 text-accent-1" />
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-8">
        <motion.div {...slideFade}>
          {children || (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8 border border-dashed border-border rounded-lg bg-surface">
              <div className="w-16 h-16 rounded-xl bg-surface border border-border flex items-center justify-center mb-4 shadow-1">
                <Sparkles className="w-8 h-8 text-accent-1" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Welcome to DriveSeed</h2>
              <p className="text-sm text-text-muted max-w-md">
                Fast server downloads streamed straight to your Google Drive. The pipeline is ready for core integrations.
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
