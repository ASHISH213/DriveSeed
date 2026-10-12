import React from "react";
import { Sliders, LogIn, AlertCircle } from "lucide-react";
import { ApiTokensCard } from "@/components/settings/ApiTokensCard";
import { WebhooksCard } from "@/components/settings/WebhooksCard";
import { RssFeedsCard } from "@/components/settings/RssFeedsCard";
import { useAuth } from "@/hooks/useAuth";

export const Settings: React.FC = () => {
  const { user, isLoading: isAuthLoading, login } = useAuth();

  if (isAuthLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-xs text-text-muted">
        Loading settings...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center max-w-md mx-auto px-4">
        <div className="w-12 h-12 rounded-xl bg-accent-1/10 flex items-center justify-center text-accent-1 mb-4">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-base font-semibold text-text">Sign in to manage settings</h2>
        <p className="text-xs text-text-muted mt-1.5 mb-6">
          Access your personal API tokens, notification webhooks, and automation configuration.
        </p>
        <button
          type="button"
          onClick={login}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-1 text-white text-xs font-medium hover:bg-accent-1/90 transition shadow-sm"
        >
          <LogIn className="w-4 h-4" />
          <span>Sign In with Google</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto" data-testid="settings-page">
      <div className="flex items-center gap-2.5 pb-2">
        <div className="p-2 rounded-lg bg-accent-1/10 text-accent-1">
          <Sliders className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-text">Settings & Automation</h1>
          <p className="text-xs text-text-muted">
            Configure personal access tokens and automation preferences for DriveSeed.
          </p>
        </div>
      </div>

      <ApiTokensCard />
      <WebhooksCard />
      <RssFeedsCard />
    </div>
  );
};

export default Settings;

