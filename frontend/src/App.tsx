import { AppShell } from "@/components/AppShell";

export function App() {
  return (
    <AppShell>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8 border border-dashed border-border rounded-lg bg-surface">
        <div className="w-16 h-16 rounded-xl bg-surface border border-border flex items-center justify-center mb-4 shadow-1">
          <div className="w-8 h-8 rounded-full bg-accent-grad animate-pulse" />
        </div>
        <h1 className="text-2xl font-semibold mb-2 tracking-tight">DriveSeed</h1>
        <p className="text-sm text-text-muted max-w-md">
          High-performance seedbox pipeline connected directly to your Google Drive.
        </p>
      </div>
    </AppShell>
  );
}

export default App;
