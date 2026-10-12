/**
 * PWA Registration & Installability Helper for DriveSeed
 */

// Global beforeinstallprompt event holder
let deferredPrompt: BeforeInstallPromptEvent | null = null;
const listeners = new Set<(canInstall: boolean) => void>();

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function initPwaInstallPrompt(): void {
  if (typeof window === "undefined") return;

  window.addEventListener("beforeinstallprompt", (e: Event) => {
    e.preventDefault();
    deferredPrompt = e as BeforeInstallPromptEvent;
    listeners.forEach((listener) => listener(true));
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    listeners.forEach((listener) => listener(false));
  });
}

export function canInstallPwa(): boolean {
  return deferredPrompt !== null;
}

export async function promptPwaInstall(): Promise<boolean> {
  if (!deferredPrompt) return false;
  try {
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    deferredPrompt = null;
    listeners.forEach((listener) => listener(false));
    return outcome === "accepted";
  } catch (err) {
    console.error("PWA install prompt failed:", err);
    return false;
  }
}

export function subscribePwaInstall(callback: (canInstall: boolean) => void): () => void {
  listeners.add(callback);
  callback(canInstallPwa());
  return () => {
    listeners.delete(callback);
  };
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.register("/sw.js", {
      scope: "/",
    });
    return registration;
  } catch (error) {
    console.warn("ServiceWorker registration skipped or failed:", error);
    return null;
  }
}
