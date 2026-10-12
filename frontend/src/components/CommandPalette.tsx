import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  Download,
  Folder,
  Plus,
  Moon,
  Sun,
  LogIn,
  LogOut,
  Play,
  File,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  Command,
  X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";
import { useAuth } from "@/hooks/useAuth";
import { useTasks } from "@/hooks/useTasks";
import { formatBytes } from "@/lib/format";
import { isMediaFile } from "@/lib/fileIcons";
import type { LibraryItem } from "@/types/library";
import type { User } from "@/hooks/useAuth";

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateTab: (tab: "downloads" | "library") => void;
  onPlayFile?: (file: LibraryItem) => void;
  onOpenAddDownload?: () => void;
  onToggleTheme?: () => void;
  isDarkTheme?: boolean;
  user?: User | null;
  onLogin?: () => void;
  onLogout?: () => void;
}

interface PaletteActionItem {
  type: "action";
  id: string;
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  category: "Navigation" | "Actions";
  execute: () => void;
}

interface PaletteTaskItem {
  type: "task";
  id: string;
  title: string;
  subtitle?: string;
  state: string;
  progress: number;
  icon: React.ReactNode;
  category: "Downloads";
  execute: () => void;
}

interface PaletteFileItem {
  type: "file";
  id: string;
  title: string;
  subtitle?: string;
  isFolder: boolean;
  isMedia: boolean;
  icon: React.ReactNode;
  category: "Drive Files";
  execute: () => void;
}

type PaletteItem = PaletteActionItem | PaletteTaskItem | PaletteFileItem;

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onNavigateTab,
  onPlayFile,
  onOpenAddDownload,
  onToggleTheme,
  isDarkTheme = true,
  user: propUser,
  onLogin: propLogin,
  onLogout: propLogout,
}) => {
  const auth = useAuth();
  const user = propUser !== undefined ? propUser : auth.user;
  const login = propLogin || auth.login;
  const logout = propLogout || auth.logout;
  const { tasks } = useTasks(!!user);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [searchResults, setSearchResults] = useState<LibraryItem[]>([]);
  const [isSearchingFiles, setIsSearchingFiles] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const { modal } = useMotionPreset();

  // Reset state on open/close
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setSearchResults([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Global Escape key listener to close palette from anywhere
  useEffect(() => {
    if (!isOpen) return;
    const handleGlobalEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleGlobalEscape);
    return () => window.removeEventListener("keydown", handleGlobalEscape);
  }, [isOpen, onClose]);

  // Debounced Drive file search when query has 2+ characters
  useEffect(() => {
    if (!isOpen || !user || query.trim().length < 2) {
      setSearchResults([]);
      setIsSearchingFiles(false);
      return;
    }

    const controller = new AbortController();
    setIsSearchingFiles(true);

    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/files?search=${encodeURIComponent(query.trim())}`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
        if (res.ok) {
          const data = (await res.json()) as { files?: LibraryItem[] };
          setSearchResults(data.files || []);
        }
      } catch {
        // Ignored aborted or network error
      } finally {
        setIsSearchingFiles(false);
      }
    }, 200);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [query, isOpen, user]);

  // Compile available actions based on auth and theme
  const actions: PaletteActionItem[] = useMemo(() => {
    const list: PaletteActionItem[] = [
      {
        type: "action",
        id: "nav-downloads",
        title: "Go to Downloads",
        subtitle: "View active downloads, progress, and speed",
        icon: <Download className="w-4 h-4 text-accent-1" />,
        category: "Navigation",
        execute: () => {
          onNavigateTab("downloads");
          onClose();
        },
      },
      {
        type: "action",
        id: "nav-library",
        title: "Go to Drive Library",
        subtitle: "Browse saved files, folders, and media",
        icon: <Folder className="w-4 h-4 text-accent-2" />,
        category: "Navigation",
        execute: () => {
          onNavigateTab("library");
          onClose();
        },
      },
    ];

    if (onOpenAddDownload) {
      list.push({
        type: "action",
        id: "action-add",
        title: "Add New Download",
        subtitle: "Paste magnet URI or direct HTTP/HTTPS URL",
        icon: <Plus className="w-4 h-4 text-accent-1" />,
        category: "Actions",
        execute: () => {
          onOpenAddDownload();
          onClose();
        },
      });
    }

    if (onToggleTheme) {
      list.push({
        type: "action",
        id: "action-theme",
        title: isDarkTheme ? "Switch to Light Mode" : "Switch to Dark Mode",
        subtitle: "Toggle interface appearance",
        icon: isDarkTheme ? (
          <Sun className="w-4 h-4 text-warning" />
        ) : (
          <Moon className="w-4 h-4 text-accent-1" />
        ),
        category: "Actions",
        execute: () => {
          onToggleTheme();
          onClose();
        },
      });
    }

    if (user) {
      list.push({
        type: "action",
        id: "action-logout",
        title: "Sign Out",
        subtitle: `Currently signed in as ${user.email}`,
        icon: <LogOut className="w-4 h-4 text-danger" />,
        category: "Actions",
        execute: () => {
          logout();
          onClose();
        },
      });
    } else {
      list.push({
        type: "action",
        id: "action-login",
        title: "Sign In with Google",
        subtitle: "Connect Google Drive account for downloads and streaming",
        icon: <LogIn className="w-4 h-4 text-accent-1" />,
        category: "Actions",
        execute: () => {
          login();
          onClose();
        },
      });
    }

    return list;
  }, [
    onNavigateTab,
    onClose,
    onOpenAddDownload,
    onToggleTheme,
    isDarkTheme,
    user,
    login,
    logout,
  ]);

  // Filter actions, tasks, and files based on query
  const items: PaletteItem[] = useMemo(() => {
    const q = query.toLowerCase().trim();

    // 1. Matched actions
    const matchedActions = actions.filter(
      (a) => !q || a.title.toLowerCase().includes(q) || (a.subtitle && a.subtitle.toLowerCase().includes(q))
    );

    // 2. Matched tasks
    const matchedTasks: PaletteTaskItem[] = tasks
      .filter((t) => !q || t.name.toLowerCase().includes(q) || t.state.toLowerCase().includes(q))
      .slice(0, 5)
      .map((t) => {
        const isCompleted = t.state === "completed";
        const isFailed = t.state === "failed";
        const icon = isCompleted ? (
          <CheckCircle2 className="w-4 h-4 text-success" />
        ) : isFailed ? (
          <AlertTriangle className="w-4 h-4 text-danger" />
        ) : (
          <Clock className="w-4 h-4 text-accent-1 animate-pulse" />
        );

        return {
          type: "task",
          id: `task-${t.id}`,
          title: t.name,
          subtitle: `${t.state.toUpperCase()} · ${Math.round((t.progress || 0) * 100)}%${
            t.total_bytes ? ` · ${formatBytes(t.total_bytes)}` : ""
          }`,
          state: t.state,
          progress: t.progress || 0,
          icon,
          category: "Downloads",
          execute: () => {
            onNavigateTab("downloads");
            onClose();
          },
        };
      });

    // 3. Matched Drive files
    const matchedFiles: PaletteFileItem[] = searchResults.slice(0, 8).map((f) => {
      const isMedia = isMediaFile(f.name, f.mime_type);
      return {
        type: "file",
        id: `file-${f.id}`,
        title: f.name,
        subtitle: f.is_folder
          ? "Folder"
          : `${isMedia ? "Media · " : ""}${formatBytes(f.size_bytes)}`,
        isFolder: f.is_folder,
        isMedia,
        icon: f.is_folder ? (
          <Folder className="w-4 h-4 text-accent-2" />
        ) : isMedia ? (
          <Play className="w-4 h-4 text-accent-1" />
        ) : (
          <File className="w-4 h-4 text-text-muted" />
        ),
        category: "Drive Files",
        execute: () => {
          if (isMedia && onPlayFile) {
            onPlayFile(f);
            onClose();
          } else {
            onNavigateTab("library");
            onClose();
          }
        },
      };
    });

    return [...matchedActions, ...matchedTasks, ...matchedFiles];
  }, [query, actions, tasks, searchResults, onNavigateTab, onClose, onPlayFile]);

  // Keep selected index in bounds when items list changes
  useEffect(() => {
    setSelectedIndex((prev) => (prev >= items.length ? Math.max(0, items.length - 1) : prev));
  }, [items.length]);

  // Handle keyboard navigation: ArrowUp, ArrowDown, Enter, Escape
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (items.length ? (prev + 1) % items.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (items.length ? (prev - 1 + items.length) % items.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (items[selectedIndex]) {
        items[selectedIndex].execute();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    }
  };

  // Group items by category for clean visual sections
  const groupedCategories = useMemo(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of items) {
      const current = map.get(item.category) || [];
      current.push(item);
      map.set(item.category, current);
    }
    return Array.from(map.entries());
  }, [items]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        role="dialog"
        aria-modal="true"
        aria-label="Command Palette"
        data-testid="command-palette-backdrop"
      >
        <motion.div
          {...modal}
          onClick={(e) => e.stopPropagation()}
          className="w-full max-w-xl rounded-xl bg-bg-elevated border border-border shadow-2 overflow-hidden flex flex-col max-h-[80vh]"
        >
          {/* Search Header */}
          <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border bg-surface/50">
            <Search className="w-5 h-5 text-text-muted flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search downloads, files, or type a command..."
              className="flex-1 bg-transparent text-sm sm:text-base text-text placeholder-text-muted focus:outline-none"
              aria-label="Search command palette"
              data-testid="command-palette-input"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="p-1 rounded-md hover:bg-surface-hover text-text-muted hover:text-text transition-colors"
                aria-label="Clear query"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono rounded bg-surface border border-border text-text-muted">
              ESC
            </kbd>
          </div>

          {/* Results List */}
          <div
            ref={listRef}
            className="flex-1 overflow-y-auto p-2 divide-y divide-border/20 text-xs sm:text-sm"
            role="listbox"
            data-testid="command-palette-list"
          >
            {items.length === 0 ? (
              <div className="p-8 text-center text-text-muted flex flex-col items-center gap-2">
                <Command className="w-6 h-6 opacity-40" />
                <p>No results found for &ldquo;{query}&rdquo;</p>
                <span className="text-xs opacity-75">
                  Try searching for a different file, task, or action.
                </span>
              </div>
            ) : (
              groupedCategories.map(([category, categoryItems]) => (
                <div key={category} className="py-1">
                  <div className="px-3 py-1.5 text-[10px] uppercase font-semibold tracking-wider text-text-muted">
                    {category}
                    {category === "Drive Files" && isSearchingFiles && (
                      <span className="ml-2 lowercase font-normal italic opacity-60">
                        searching...
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col gap-0.5">
                    {categoryItems.map((item) => {
                      const itemIndex = items.indexOf(item);
                      const isSelected = itemIndex === selectedIndex;

                      return (
                        <button
                          key={item.id}
                          type="button"
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => item.execute()}
                          onMouseEnter={() => setSelectedIndex(itemIndex)}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors ${
                            isSelected
                              ? "bg-accent-1/15 text-text border border-accent-1/30 shadow-sm"
                              : "text-text hover:bg-surface border border-transparent"
                          }`}
                          data-testid={`command-item-${item.id}`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="p-1.5 rounded-md bg-surface border border-border flex items-center justify-center flex-shrink-0">
                              {item.icon}
                            </div>
                            <div className="flex flex-col min-w-0">
                              <span className="font-medium text-xs sm:text-sm truncate">
                                {item.title}
                              </span>
                              {item.subtitle && (
                                <span className="text-[11px] text-text-muted truncate">
                                  {item.subtitle}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-1 text-text-muted flex-shrink-0 ml-2">
                            {isSelected && (
                              <ArrowRight className="w-3.5 h-3.5 text-accent-1 animate-pulse" />
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer Shortcuts Info */}
          <div className="px-4 py-2 border-t border-border bg-surface/40 flex items-center justify-between text-[11px] text-text-muted font-mono">
            <div className="flex items-center gap-3">
              <span>
                <kbd className="px-1 py-0.5 rounded bg-surface border border-border">↑</kbd>
                <kbd className="px-1 py-0.5 rounded bg-surface border border-border ml-1">↓</kbd> navigate
              </span>
              <span>
                <kbd className="px-1 py-0.5 rounded bg-surface border border-border">↵</kbd> select
              </span>
            </div>
            <span>
              <kbd className="px-1 py-0.5 rounded bg-surface border border-border">esc</kbd> close
            </span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
