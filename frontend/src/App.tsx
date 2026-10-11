import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { Library } from "@/pages/Library";

export type NavTab = "downloads" | "library";

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("downloads");

  return (
    <AppShell activeTab={activeTab} onTabChange={setActiveTab}>
      {activeTab === "downloads" ? <Dashboard /> : <Library />}
    </AppShell>
  );
}

export default App;

