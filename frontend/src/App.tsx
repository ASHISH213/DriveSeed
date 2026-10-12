import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AppShell } from "@/components/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { Library } from "@/pages/Library";
import { PlayerModal } from "@/components/player/PlayerModal";
import type { LibraryItem } from "@/types/library";
import { duration, ease } from "@/lib/motion";

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
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: duration.base, ease: ease.out }}
          >
            {activeTab === "downloads" ? <Dashboard /> : <Library />}
          </motion.div>
        </AnimatePresence>
      </AppShell>

      <PlayerModal
        file={activePlayFile}
        onClose={() => setActivePlayFile(null)}
      />
    </>
  );
}

export default App;
