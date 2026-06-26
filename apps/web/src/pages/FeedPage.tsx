import { useEffect, useRef } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { FeedItem, Prompt } from "../api/types";
import { PostCard } from "../components/PostCard";

const PAGE_SIZE = 8;

export function FeedPage() {
  const [params, setParams] = useSearchParams();
  const topicId = params.get("topic");

  if (topicId) return <TopicFeed topicId={topicId} onClear={() => setParams({})} />;
  return <MainFeed />;
}

/** The default, server-stateful feed: paged, advances progress, marks seen. */
function MainFeed() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
  } = useInfiniteQuery({
    queryKey: ["feed"],
    initialPageParam: 0,
    queryFn: () => api.feed(PAGE_SIZE),
    // The server tracks "seen" state, so each call returns the next batch.
    // We keep paging until a call comes back short/empty.
    getNextPageParam: (lastPage, pages) =>
      lastPage.items.length >= PAGE_SIZE ? pages.length : undefined,
  });

  const items: FeedItem[] = data?.pages.flatMap((p) => p.items) ?? [];
  const exhausted = data?.pages.some((p) => p.exhausted) ?? false;
  const sentinel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (isLoading) return <div className="center muted">Loading your feed…</div>;
  if (isError) return <div className="center error">Couldn't load the feed.</div>;

  if (items.length === 0) {
    return (
      <div className="center empty">
        <h2>Your feed is empty</h2>
        <p className="muted">
          Tell us what you want to learn, or pick some interests to get suggestions.
        </p>
        <div className="empty-actions">
          <Link className="primary" to="/discover">Request a topic</Link>
          <Link className="ghost" to="/interests">Pick interests</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="feed">
      {exhausted && (
        <div className="feed-banner">
          <strong>You've covered everything ✦</strong>
          <span className="muted">
            You're all caught up on every topic — the posts below are repeats.
          </span>
          <span className="muted">
            <Link to="/discover">Request a new topic</Link> to generate fresh ones.
          </span>
        </div>
      )}
      {/* Repeats can reuse a post_id across pages, so the key includes the index. */}
      {items.map((item, idx) => (
        <PostCard key={`${idx}-${item.post.post_id}`} item={item} />
      ))}
      <div ref={sentinel} className="sentinel">
        {isFetchingNextPage ? "Loading more…" : hasNextPage ? "" : "You're all caught up ✦"}
      </div>
    </div>
  );
}

/** The feed scoped to one topic: unvisited posts first, then visited. Read-only
 *  (the server doesn't advance progress here), so it's not paged — a topic's
 *  posts are bounded, so we render them all. */
function TopicFeed({ topicId, onClear }: { topicId: string; onClear: () => void }) {
  const feed = useQuery({
    queryKey: ["topicFeed", topicId],
    queryFn: () => api.topicFeed(topicId),
  });

  // Label the filter with the user's original request text. listPrompts is
  // already cached from the Discover page; fall back to the topic id.
  const prompts = useQuery({ queryKey: ["prompts"], queryFn: api.listPrompts });
  const label =
    prompts.data?.find((p: Prompt) => p.topic_id === topicId)?.prompt_text ?? topicId;

  const items: FeedItem[] = feed.data?.items ?? [];

  return (
    <div className="feed">
      <div className="filter-bar">
        <span className="filter-chip">
          <span className="filter-chip-label">
            Filtered: <strong>{label}</strong>
          </span>
          <button className="filter-clear" onClick={onClear} aria-label="Clear topic filter">
            Clear ✕
          </button>
        </span>
        <span className="muted small">Unvisited posts first, then ones you've seen.</span>
      </div>

      {feed.isLoading ? (
        <div className="center muted">Loading this topic…</div>
      ) : feed.isError ? (
        <div className="center error">Couldn't load this topic.</div>
      ) : items.length === 0 ? (
        <div className="center empty">
          <h2>Nothing here yet</h2>
          <p className="muted">This topic has no posts to show.</p>
          <div className="empty-actions">
            <button className="ghost" onClick={onClear}>Back to your feed</button>
          </div>
        </div>
      ) : (
        items.map((item, idx) => (
          <PostCard key={`${idx}-${item.post.post_id}`} item={item} />
        ))
      )}
    </div>
  );
}
