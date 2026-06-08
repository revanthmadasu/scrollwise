import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Topic } from "../api/types";

export function InterestsPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const topics = useQuery({ queryKey: ["topics"], queryFn: api.topics });
  const current = useQuery({ queryKey: ["interests"], queryFn: api.getInterests });

  useEffect(() => {
    if (current.data) setSelected(new Set(current.data.topic_ids));
  }, [current.data]);

  const save = useMutation({
    mutationFn: () => api.setInterests([...selected]),
    onSuccess: () => navigate("/"),
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div className="page narrow">
      <h1>Pick your interests</h1>
      <p className="muted">
        We'll mix in trending, highly-liked posts from these topics to keep your feed fresh.
      </p>

      {topics.isLoading ? (
        <div className="muted">Loading topics…</div>
      ) : topics.data && topics.data.length > 0 ? (
        <div className="topic-grid">
          {topics.data.map((t: Topic) => (
            <button
              key={t.topic_id}
              className={`topic-tile ${selected.has(t.topic_id) ? "on" : ""}`}
              onClick={() => toggle(t.topic_id)}
            >
              <span className="topic-title">{t.title}</span>
              <span className="topic-desc muted">{t.description}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="muted">
          No topics available yet — the content generator hasn't produced any curricula.
        </p>
      )}

      <div className="page-actions">
        <button className="primary" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save & go to feed"}
        </button>
      </div>
    </div>
  );
}
