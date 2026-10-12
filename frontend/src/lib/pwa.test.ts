import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  registerServiceWorker,
  initPwaInstallPrompt,
  subscribePwaInstall,
  promptPwaInstall,
  canInstallPwa,
} from "./pwa";

describe("PWA Service Worker & Installability (M3b.3)", () => {
  const originalNavigator = global.navigator;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(global, "navigator", {
      value: originalNavigator,
      writable: true,
    });
  });

  it("handles registration gracefully when serviceWorker is supported", async () => {
    const mockRegister = vi.fn().mockResolvedValue({
      scope: "/",
    } as ServiceWorkerRegistration);

    Object.defineProperty(global, "navigator", {
      value: {
        ...originalNavigator,
        serviceWorker: {
          register: mockRegister,
        },
      },
      writable: true,
    });

    const reg = await registerServiceWorker();
    expect(mockRegister).toHaveBeenCalledWith("/sw.js", { scope: "/" });
    expect(reg).toBeDefined();
  });

  it("returns null when serviceWorker is not supported in navigator", async () => {
    Object.defineProperty(global, "navigator", {
      value: {},
      writable: true,
    });

    const reg = await registerServiceWorker();
    expect(reg).toBeNull();
  });

  it("captures beforeinstallprompt and notifies subscribers", async () => {
    initPwaInstallPrompt();
    let installableState = false;

    const unsubscribe = subscribePwaInstall((canInstall) => {
      installableState = canInstall;
    });

    expect(canInstallPwa()).toBe(false);

    // Simulate beforeinstallprompt event
    const mockPrompt = vi.fn().mockResolvedValue(undefined);
    const mockEvent = new Event("beforeinstallprompt") as unknown as {
      prompt: () => Promise<void>;
      userChoice: Promise<{ outcome: string }>;
      preventDefault: () => void;
    };
    mockEvent.prompt = mockPrompt;
    mockEvent.userChoice = Promise.resolve({ outcome: "accepted" });
    mockEvent.preventDefault = vi.fn();

    window.dispatchEvent(mockEvent as unknown as Event);

    expect(canInstallPwa()).toBe(true);
    expect(installableState).toBe(true);

    // Trigger installation
    const installed = await promptPwaInstall();
    expect(installed).toBe(true);
    expect(mockPrompt).toHaveBeenCalledTimes(1);
    expect(canInstallPwa()).toBe(false);

    unsubscribe();
  });
});
