import { useLayoutEffect, useRef, useState } from "react";
import type { TouchEvent } from "react";
import type { FeedItem, FeedReason } from "../api/types";
import { ReactionBar } from "./ReactionBar";
import { TestCard } from "./TestCard";
import { TemplateRenderer } from "../templates/TemplateRenderer";
import { TEMPLATE_BY_ID } from "../templates/defs";

const REASON_LABEL: Record<FeedReason, string> = {
  prompted: "From your request",
  remediation: "Revisit",
  suggested: "Suggested for you",
};

const LEVEL_LABEL: Record<number, string> = { 1: "Summary", 2: "Standard", 3: "Deep dive" };

const SWIPE_THRESHOLD = 40; // px of horizontal travel to count as a swipe

function Carousel({ images }: { images: string[] }) {
  const [i, setI] = useState(0);
  const start = useRef<{ x: number; y: number } | null>(null);

  if (images.length === 0) return null;

  const go = (dir: number) => setI((prev) => (prev + dir + images.length) % images.length);

  function onTouchStart(e: TouchEvent) {
    const t = e.touches[0];
    start.current = { x: t.clientX, y: t.clientY };
  }
  function onTouchEnd(e: TouchEvent) {
    if (!start.current) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - start.current.x;
    const dy = t.clientY - start.current.y;
    start.current = null;
    // Only act on a horizontal-dominant swipe, so vertical feed scrolling is untouched.
    if (Math.abs(dx) > SWIPE_THRESHOLD && Math.abs(dx) > Math.abs(dy)) {
      go(dx < 0 ? 1 : -1);
    }
  }

  return (
    <div className="carousel" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      <div className="carousel-track" style={{ transform: `translateX(-${i * 100}%)` }}>
        {images.map((src, n) => (
          <img key={n} src={src} alt="" draggable={false} />
        ))}
      </div>
      {images.length > 1 && (
        <>
          <button className="car-nav left" onClick={() => go(-1)} aria-label="Previous image">
            ‹
          </button>
          <button className="car-nav right" onClick={() => go(1)} aria-label="Next image">
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

  // Data-driven rendering: when the generator assigned an approved template
  // (and the client still recognizes it), render through the engine instead
  // of the legacy image+text layout. Falls through on an unknown/older id.
  if (post.template_id && TEMPLATE_BY_ID[post.template_id]) {
    return (
      <article className="card">
        <header className="card-head">
          <ReasonBadge reason={reason} />
          <span className="level-chip">{LEVEL_LABEL[post.level] ?? `L${post.level}`}</span>
        </header>
        <TemplateRenderer templateId={post.template_id} inputs={post.template_inputs} />
        <footer className="card-foot">
          <ReactionBar post={post} />
          <span className="duration muted">{post.estimated_duration_sec}s read</span>
        </footer>
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
