import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { Library } from "@/pages/Library";
import { PlayerModal } from "@/components/player/PlayerModal";
import type { LibraryItem } from "@/types/library";

export type NavTab = "downloads" | "library";

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("downloads");
  const [activePlayFile, setActivePlayFile] = useState<LibraryItem | null>(null);

  return (
    <>
      <AppShell
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onPlayFile={(file) => setActivePlayFile(file)}
      >
        {activeTab === "downloads" ? <Dashboard /> : <Library />}
      </AppShell>

      <PlayerModal
        file={activePlayFile}
        onClose={() => setActivePlayFile(null)}
      />
    </>
  );
}

export default App;

