import React, { useEffect, useState } from "react";
import { Moon, Sun, Sparkles, LogIn, LogOut, User as UserIcon, Download, Folder, Search } from "lucide-react";
import { motion } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";
import { useAuth } from "@/hooks/useAuth";
import { StorageRing } from "@/components/StorageRing";
import { CommandPalette } from "@/components/CommandPalette";
import type { LibraryItem } from "@/types/library";

export type Theme = "dark" | "light";

interface AppShellProps {
  activeTab?: "downloads" | "library";
  onTabChange?: (tab: "downloads" | "library") => void;
  onPlayFile?: (file: LibraryItem) => void;
  children?: React.ReactNode;
}

export function AppShell({ activeTab = "downloads", onTabChange, onPlayFile, children }: AppShellProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("driveseed-theme") as Theme | null;
      if (saved === "light" || saved === "dark") return saved;
      return "dark";
    }
    return "dark";
  });
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);

  const { user, isLoading, login, logout } = useAuth();

  // Global Ctrl+K / Cmd+K shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
          <div className="flex items-center gap-2 sm:gap-4">
            {/* Command Palette Trigger */}
            <button
              type="button"
              onClick={() => setIsPaletteOpen(true)}
              data-testid="command-palette-trigger"
              className="flex items-center gap-2 px-2.5 sm:px-3 py-1.5 rounded-lg bg-surface border border-border text-text-muted hover:text-text hover:border-accent-1/40 text-xs transition-all shadow-sm"
              aria-label="Open command palette"
              title="Search or commands (Ctrl+K)"
            >
              <Search className="w-3.5 h-3.5 text-text-muted" />
              <span className="hidden sm:inline text-xs">Search...</span>
              <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-bg rounded border border-border text-text-muted">
                ⌘K
              </kbd>
            </button>

            {/* Storage Meter Ring */}
            <StorageRing isLoggedIn={!!user} />

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

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onNavigateTab={(tab) => {
          onTabChange?.(tab);
          setIsPaletteOpen(false);
        }}
        onPlayFile={onPlayFile}
        onOpenAddDownload={() => {
          onTabChange?.("downloads");
          setIsPaletteOpen(false);
        }}
        onToggleTheme={toggleTheme}
        isDarkTheme={theme === "dark"}
        user={user}
        onLogin={login}
        onLogout={logout}
      />
    </div>
  );
}
