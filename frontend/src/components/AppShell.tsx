import React, { useEffect, useState } from "react";
import { Moon, Sun, HardDrive, Sparkles, LogIn, LogOut, User as UserIcon, Download, Folder } from "lucide-react";
import { motion } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";
import { useAuth } from "@/hooks/useAuth";

export type Theme = "dark" | "light";

interface AppShellProps {
  activeTab?: "downloads" | "library";
  onTabChange?: (tab: "downloads" | "library") => void;
  children?: React.ReactNode;
}

export function AppShell({ activeTab = "downloads", onTabChange, children }: AppShellProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("driveseed-theme") as Theme | null;
      if (saved === "light" || saved === "dark") return saved;
      return "dark";
    }
    return "dark";
  });

  const { user, isLoading, login, logout } = useAuth();

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
          {/* Logo, Brand & Navigation */}
          <div className="flex items-center gap-4 sm:gap-6">
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

            {/* Navigation Tabs */}
            {onTabChange && (
              <nav className="flex items-center gap-1 bg-surface p-1 rounded-lg border border-border" data-testid="nav-tabs">
                <button
                  type="button"
                  onClick={() => onTabChange("downloads")}
                  data-testid="nav-tab-downloads"
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === "downloads"
                      ? "bg-accent-1 text-white shadow-sm"
                      : "text-text-muted hover:text-text hover:bg-surface-hover"
                  }`}
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Downloads</span>
                </button>
                <button
                  type="button"
                  onClick={() => onTabChange("library")}
                  data-testid="nav-tab-library"
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    activeTab === "library"
                      ? "bg-accent-1 text-white shadow-sm"
                      : "text-text-muted hover:text-text hover:bg-surface-hover"
                  }`}
                >
                  <Folder className="w-3.5 h-3.5" />
                  <span>Library</span>
                </button>
              </nav>
            )}
          </div>

          {/* Right Controls: Storage Indicator, Auth Status & Theme Toggle */}
          <div className="flex items-center gap-3 sm:gap-4">
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

            {/* User Auth Section */}
            {isLoading ? (
              <div className="w-24 h-8 rounded-md bg-surface animate-pulse" />
            ) : user ? (
              <div className="flex items-center gap-2">
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface border border-border"
                  data-testid="user-profile"
                >
                  <UserIcon className="w-3.5 h-3.5 text-accent-1" />
                  <span className="text-xs font-medium text-text max-w-[140px] sm:max-w-[180px] truncate">
                    {user.email}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={logout}
                  aria-label="Log out"
                  data-testid="logout-button"
                  className="p-2 rounded-md bg-surface border border-border hover:bg-surface-hover hover:text-danger text-text-muted transition-colors"
                  title="Log out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={login}
                data-testid="login-button"
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-surface border border-border hover:bg-surface-hover hover:shadow-glow text-xs font-medium text-text transition-all duration-150"
              >
                <LogIn className="w-3.5 h-3.5 text-accent-1" />
                <span>Sign in with Google</span>
              </button>
            )}

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
                Fast server downloads streamed straight to your Google Drive.
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
