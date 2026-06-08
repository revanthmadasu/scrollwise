import { useState } from "react";
import { api } from "../api/client";
import type { Post, Reaction } from "../api/types";

// Like / dislike footer. Clicking the active reaction clears it (toggle).
export function ReactionBar({ post }: { post: Post }) {
  const [reaction, setReaction] = useState<Reaction | null>(post.my_reaction);
  const [likes, setLikes] = useState(post.like_count);
  const [busy, setBusy] = useState(false);

  async function set(next: Reaction) {
    if (busy) return;
    const target = reaction === next ? null : next;
    setBusy(true);
    try {
      const res = await api.react(post.post_id, target);
      setReaction(res.my_reaction);
      setLikes(res.like_count);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="reactions">
      <button
        className={`react-btn ${reaction === "like" ? "active like" : ""}`}
        onClick={() => set("like")}
        aria-label="Like"
      >
        ♥ <span>{likes}</span>
      </button>
      <button
        className={`react-btn ${reaction === "dislike" ? "active dislike" : ""}`}
        onClick={() => set("dislike")}
        aria-label="Dislike"
      >
        ✕
      </button>
    </div>
  );
}
