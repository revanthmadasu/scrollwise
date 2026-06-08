import { useLayoutEffect, useRef, useState } from "react";
import type { FeedItem, FeedReason } from "../api/types";
import { ReactionBar } from "./ReactionBar";
import { TestCard } from "./TestCard";

const REASON_LABEL: Record<FeedReason, string> = {
  prompted: "From your request",
  remediation: "Revisit",
  suggested: "Suggested for you",
};

const LEVEL_LABEL: Record<number, string> = { 1: "Summary", 2: "Standard", 3: "Deep dive" };

function Carousel({ images }: { images: string[] }) {
  const [i, setI] = useState(0);
  if (images.length === 0) return null;
  return (
    <div className="carousel">
      <img src={images[i]} alt="" />
      {images.length > 1 && (
        <>
          <button className="car-nav left" onClick={() => setI((i - 1 + images.length) % images.length)}>
            ‹
          </button>
          <button className="car-nav right" onClick={() => setI((i + 1) % images.length)}>
            ›
          </button>
          <div className="dots">
            {images.map((_, n) => (
              <span key={n} className={n === i ? "dot active" : "dot"} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function PostCard({ item }: { item: FeedItem }) {
  const { post, reason } = item;

  if (post.content_type === "test") {
    return (
      <article className="card test-card">
        <ReasonBadge reason={reason} />
        <TestCard post={post} />
      </article>
    );
  }

  // Prefer rendered cards, fall back to raw backgrounds.
  const images = post.post_image_urls.length ? post.post_image_urls : post.image_urls;

  return (
    <article className="card">
      <header className="card-head">
        <ReasonBadge reason={reason} />
        <span className="level-chip">{LEVEL_LABEL[post.level] ?? `L${post.level}`}</span>
      </header>

      {post.content_type === "video" && post.video_url ? (
        <video className="media" src={post.video_url} controls playsInline />
      ) : images.length > 0 ? (
        <Carousel images={images} />
      ) : null}

      <div className="card-body">
        <h2 className="card-title">{post.title}</h2>
        <ExpandableText text={post.body} />
      </div>

      <footer className="card-foot">
        <ReactionBar post={post} />
        <span className="duration muted">{post.estimated_duration_sec}s read</span>
      </footer>
    </article>
  );
}

function ReasonBadge({ reason }: { reason: FeedReason }) {
  return <span className={`reason ${reason}`}>{REASON_LABEL[reason]}</span>;
}

/** Post body collapsed to 2 lines, with a "See more" toggle shown only when the
 *  text actually overflows the clamp. */
function ExpandableText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  // Measure against the clamped height. Skip while expanded (the clamp is off,
  // so scrollHeight would equal clientHeight and falsely report no overflow);
  // `overflowing` retains its collapsed-state value so the toggle stays put.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || expanded) return;
    const measure = () => setOverflowing(el.scrollHeight > el.clientHeight + 1);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [text, expanded]);

  return (
    <div className="card-text-wrap">
      <p ref={ref} className={expanded ? "card-text" : "card-text clamped"}>
        {text}
      </p>
      {overflowing && (
        <button className="see-more" onClick={() => setExpanded((e) => !e)}>
          {expanded ? "See less" : "See more"}
        </button>
      )}
    </div>
  );
}
