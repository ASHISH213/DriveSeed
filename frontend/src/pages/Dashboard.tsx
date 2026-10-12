import React, { useState } from "react";
import { Sparkles, Radio, AlertCircle, RefreshCw, LogIn } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { AddBox } from "@/components/AddBox";
import { TaskCard } from "@/components/TaskCard";
import { FileSelectionModal } from "@/components/selection/FileSelectionModal";
import { SystemAlerts } from "@/components/SystemAlerts";
import { useTasks } from "@/hooks/useTasks";
import { useAuth } from "@/hooks/useAuth";
import { useMotionPreset } from "@/lib/motion";

export const Dashboard: React.FC = () => {
  const { user, isLoading: isAuthLoading, login } = useAuth();
  const {
    tasks,
    isLoading: isTasksLoading,
    error,
    isSseConnected,
    refreshTasks,
    createTask,
    startTask,
    pauseTask,
    resumeTask,
    cancelTask,
    retryTask,
  } = useTasks(!!user);

  const [modalTaskId, setModalTaskId] = useState<string | null>(null);
  const selectedTaskForModal = modalTaskId ? tasks.find((t) => t.id === modalTaskId) ?? null : null;

  const { slideFade } = useMotionPreset();

  return (
    <div className="w-full max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8 flex flex-col gap-8">
      {/* System Edge State Alerts (Offline, Drive full, Drive disconnected) */}
      <SystemAlerts />

      {/* Hero / Add Section */}
      <section className="flex flex-col items-center text-center gap-4">
        <motion.div {...slideFade} className="flex flex-col items-center gap-2 max-w-xl">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border text-xs text-text-muted font-mono">
            <Radio
              className={`w-3.5 h-3.5 ${
                isSseConnected ? "text-success animate-pulse" : "text-text-muted"
              }`}
            />
            <span>{isSseConnected ? "Live SSE Connected" : "Connecting Live Feed..."}</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            Server Download &amp; Drive Seeder
          </h1>
          <p className="text-xs sm:text-sm text-text-muted">
            Directly download high-speed torrents and web files into your Google Drive storage.
          </p>
        </motion.div>

        {/* Unauthenticated notice */}
        {!isAuthLoading && !user && (
          <motion.div
            {...slideFade}
            className="w-full max-w-xl p-6 rounded-xl bg-surface border border-border text-center flex flex-col items-center gap-3 shadow-1"
          >
            <div className="w-10 h-10 rounded-full bg-accent-1/10 flex items-center justify-center text-accent-1">
              <LogIn className="w-5 h-5" />
            </div>
            <h2 className="text-base font-semibold text-text">Sign In with Google to Start</h2>
            <p className="text-xs text-text-muted max-w-sm">
              DriveSeed saves downloads directly into your Google Drive. Sign in to link your account.
            </p>
            <button
              type="button"
              onClick={login}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-grad text-white text-xs font-semibold shadow-glow hover:opacity-95 transition-opacity"
            >
              Sign In with Google
            </button>
          </motion.div>
        )}

        {/* AddBox */}
        {user && (
          <div className="w-full">
            <AddBox
              onAdd={async (uri, name) => {
                await createTask({ source_uri: uri, name });
              }}
              disabled={!user}
            />
          </div>
        )}
      </section>

      {/* Task List Section */}
      {user && (
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-semibold text-text">Active Downloads</h2>
              <span className="px-2 py-0.5 rounded-full bg-surface border border-border text-xs font-mono text-text-muted">
                {tasks.length}
              </span>
            </div>

            <button
              type="button"
              onClick={() => refreshTasks()}
              className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors p-1.5 rounded-md hover:bg-surface"
              title="Refresh task list"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isTasksLoading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-xs">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={() => refreshTasks()}
                className="underline hover:opacity-80"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading Skeletons */}
          {isTasksLoading && tasks.length === 0 && (
            <div className="flex flex-col gap-3">
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className="h-28 rounded-xl bg-surface/50 border border-border animate-pulse p-4"
                />
              ))}
            </div>
          )}

          {/* Empty State */}
          {!isTasksLoading && tasks.length === 0 && (
            <motion.div
              {...slideFade}
              className="flex flex-col items-center justify-center p-10 sm:p-12 text-center rounded-xl bg-surface/40 border border-dashed border-border"
            >
              <div className="w-12 h-12 rounded-xl bg-surface border border-border flex items-center justify-center mb-3 text-text-muted">
                <Sparkles className="w-6 h-6 text-accent-1 opacity-70" />
              </div>
              <h3 className="font-medium text-sm sm:text-base text-text mb-1">
                No active downloads
              </h3>
              <p className="text-xs text-text-muted max-w-sm">
                Paste a magnet link or HTTP download URL in the box above to seed files straight to
                Google Drive.
              </p>
            </motion.div>
          )}

          {/* Animated Task Cards List */}
          <div className="flex flex-col gap-3">
            <AnimatePresence mode="popLayout">
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onPause={pauseTask}
                  onResume={resumeTask}
                  onCancel={cancelTask}
                  onRetry={retryTask}
                  onSelectFiles={(t) => setModalTaskId(t.id)}
                />
              ))}
            </AnimatePresence>
          </div>
        </section>
      )}

      {/* File Selection Modal */}
      <FileSelectionModal
        isOpen={!!selectedTaskForModal}
        task={selectedTaskForModal}
        onClose={() => setModalTaskId(null)}
        onStart={async (taskId, req) => {
          await startTask(taskId, req);
        }}
      />
    </div>
  );
};
