import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Prompt, PromptStatus } from "../api/types";

const STATUS_LABEL: Record<PromptStatus, string> = {
  pending: "Queued",
  generating: "Generating…",
  ready: "Ready",
  failed: "Failed",
};

export function DiscoverPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [text, setText] = useState("");

  // A ready request maps to a generated topic; clicking it opens the feed
  // filtered to that topic (unvisited posts first). Only ready requests with a
  // topic_id are navigable.
  const openTopic = (p: Prompt) => {
    if (p.status === "ready" && p.topic_id) {
      navigate(`/?topic=${encodeURIComponent(p.topic_id)}`);
    }
  };

  const prompts = useQuery({ queryKey: ["prompts"], queryFn: api.listPrompts });

  const create = useMutation({
    mutationFn: (prompt_text: string) => api.createPrompt(prompt_text),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["prompts"] });
    },
  });

  return (
    <div className="page narrow">
      <h1>What do you want to learn?</h1>
      <p className="muted">
        Describe a topic and we'll generate a bite-size course for your feed. Once it's
        ready, its posts get top priority — interleaved with checkpoints to make it stick.
      </p>

      <form
        className="prompt-composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim().length >= 3) create.mutate(text.trim());
        }}
      >
        <textarea
          placeholder="e.g. The fundamentals of options trading, explained simply"
          value={text}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
        />
        <button className="primary" disabled={create.isPending || text.trim().length < 3}>
          {create.isPending ? "Submitting…" : "Generate"}
        </button>
      </form>
      {create.isError && <div className="error">Couldn't submit that prompt.</div>}

      <h2 className="section">Your requests</h2>
      {prompts.isLoading ? (
        <div className="muted">Loading…</div>
      ) : prompts.data && prompts.data.length > 0 ? (
        <ul className="prompt-list">
          {prompts.data.map((p: Prompt) => {
            const navigable = p.status === "ready" && !!p.topic_id;
            return (
              <li
                key={p.id}
                className={`prompt-row${navigable ? " navigable" : ""}`}
                onClick={navigable ? () => openTopic(p) : undefined}
                role={navigable ? "button" : undefined}
                tabIndex={navigable ? 0 : undefined}
                onKeyDown={
                  navigable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          openTopic(p);
                        }
                      }
                    : undefined
                }
                aria-label={navigable ? `Open "${p.prompt_text}" in your feed` : undefined}
              >
                <div>
                  <div className="prompt-text">{p.prompt_text}</div>
                  <div className="muted small">{new Date(p.created_at).toLocaleString()}</div>
                  {p.status === "ready" && p.reused && (
                    <div className="reused-note">✓ Already available — added to your feed instantly</div>
                  )}
                  {navigable && <div className="prompt-cta">View in feed →</div>}
                </div>
                <span className={`status-pill ${p.status}`}>{STATUS_LABEL[p.status]}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">No requests yet.</p>
      )}
    </div>
  );
}
