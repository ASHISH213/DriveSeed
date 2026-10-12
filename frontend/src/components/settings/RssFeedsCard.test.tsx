import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { RssFeedsCard } from "./RssFeedsCard";

describe("RssFeedsCard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url, opts) => {
        const u = String(url);
        const method = opts?.method || "GET";

        if (u.endsWith("/api/rss") && method === "GET") {
          return {
            ok: true,
            status: 200,
            json: async () => [],
          } as Response;
        }

        return {
          ok: false,
          status: 404,
          json: async () => ({}),
        } as Response;
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders empty state when no RSS feeds exist", async () => {
    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByText("RSS Feeds")).toBeInTheDocument();
      expect(screen.getByText("No RSS feeds configured")).toBeInTheDocument();
    });
  });

  it("renders feeds list with name, url, and regex pattern", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/rss") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "rss-1",
              name: "Ubuntu ISOs",
              url: "https://releases.ubuntu.com/rss.xml",
              filter_regex: "(?i)ubuntu.*amd64",
              is_active: true,
              last_checked_at: "2026-10-12T12:00:00Z",
              last_item_title: "Ubuntu 24.04.1 Desktop AMD64",
              created_at: "2026-10-12T10:00:00Z",
            },
          ],
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByText("Ubuntu ISOs")).toBeInTheDocument();
      expect(screen.getByText("https://releases.ubuntu.com/rss.xml")).toBeInTheDocument();
      expect(screen.getByText("/(?i)ubuntu.*amd64/")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText(/Ubuntu 24.04.1 Desktop AMD64/)).toBeInTheDocument();
    });
  });

  it("adds a new RSS feed subscription", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/rss") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }

      if (u.endsWith("/api/rss") && method === "POST") {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: "rss-new",
            name: "Debian Releases",
            url: "https://cdimage.debian.org/feed.xml",
            filter_regex: "netinst",
            is_active: true,
            last_checked_at: null,
            last_item_title: null,
            created_at: "2026-10-12T12:00:00Z",
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByTestId("add-rss-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-rss-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("rss-name-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("rss-name-input"), {
      target: { value: "Debian Releases" },
    });
    fireEvent.change(screen.getByTestId("rss-url-input"), {
      target: { value: "https://cdimage.debian.org/feed.xml" },
    });
    fireEvent.change(screen.getByTestId("rss-regex-input"), {
      target: { value: "netinst" },
    });

    fireEvent.click(screen.getByTestId("rss-submit-btn"));

    await waitFor(() => {
      expect(screen.getByText("Debian Releases")).toBeInTheDocument();
      expect(screen.getByText("https://cdimage.debian.org/feed.xml")).toBeInTheDocument();
    });
  });

  it("previews feed matching results in modal", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/rss") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as Response;
      }

      if (u.endsWith("/api/rss/preview") && method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            feed_title: "Arch Linux ISOs",
            total_items: 2,
            matching_items: [
              {
                title: "archlinux-2026.10-x86_64.iso",
                link: "https://archlinux.org/rel.iso",
                is_match: true,
              },
              {
                title: "archlinux-source.tar.gz",
                link: "https://archlinux.org/source.tar.gz",
                is_match: false,
              },
            ],
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByTestId("add-rss-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-rss-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("rss-url-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("rss-url-input"), {
      target: { value: "https://archlinux.org/feeds/rel.xml" },
    });

    fireEvent.click(screen.getByTestId("rss-preview-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("rss-preview-result")).toBeInTheDocument();
      expect(screen.getByText("archlinux-2026.10-x86_64.iso")).toBeInTheDocument();
      expect(screen.getByText("Arch Linux ISOs")).toBeInTheDocument();
    });
  });

  it("triggers manual sync for an RSS feed", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/rss") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "rss-sync-1",
              name: "Fedora Project",
              url: "https://getfedora.org/feed.xml",
              filter_regex: null,
              is_active: true,
              last_checked_at: null,
              last_item_title: null,
              created_at: "2026-10-12T10:00:00Z",
            },
          ],
        } as Response;
      }

      if (u.endsWith("/api/rss/rss-sync-1/sync") && method === "POST") {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            subscription_id: "rss-sync-1",
            items_checked: 5,
            tasks_created: 2,
            created_task_ids: ["task-a", "task-b"],
          }),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByTestId("sync-rss-rss-sync-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("sync-rss-rss-sync-1"));

    await waitFor(() => {
      expect(screen.getByTestId("sync-result-rss-sync-1")).toBeInTheDocument();
      expect(screen.getByText(/Checked 5 items/)).toBeInTheDocument();
      expect(screen.getByText(/Created 2 new tasks/)).toBeInTheDocument();
    });
  });

  it("deletes an RSS feed subscription", async () => {
    vi.mocked(fetch).mockImplementation(async (url, opts) => {
      const u = String(url);
      const method = opts?.method || "GET";

      if (u.endsWith("/api/rss") && method === "GET") {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: "rss-del-1",
              name: "Delete Me Feed",
              url: "https://del.org/feed.xml",
              filter_regex: null,
              is_active: true,
              last_checked_at: null,
              last_item_title: null,
              created_at: "2026-10-12T10:00:00Z",
            },
          ],
        } as Response;
      }

      if (u.endsWith("/api/rss/rss-del-1") && method === "DELETE") {
        return {
          ok: true,
          status: 204,
          json: async () => ({}),
        } as Response;
      }

      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RssFeedsCard />);

    await waitFor(() => {
      expect(screen.getByText("Delete Me Feed")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("delete-rss-rss-del-1"));

    await waitFor(() => {
      expect(screen.queryByText("Delete Me Feed")).not.toBeInTheDocument();
    });
  });
});
