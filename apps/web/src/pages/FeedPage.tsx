import { useEffect, useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { FeedItem } from "../api/types";
import { PostCard } from "../components/PostCard";

const PAGE_SIZE = 8;

export function FeedPage() {
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
      {items.map((item) => (
        <PostCard key={item.post.post_id} item={item} />
      ))}
      <div ref={sentinel} className="sentinel">
        {isFetchingNextPage ? "Loading more…" : hasNextPage ? "" : "You're all caught up ✦"}
      </div>
    </div>
  );
}
