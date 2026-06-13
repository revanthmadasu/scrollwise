import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { InterestCategory } from "../api/types";

export function InterestsPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: api.categories,
  });
  const current = useQuery({
    queryKey: ["interests"],
    queryFn: api.getInterests,
  });

  useEffect(() => {
    if (current.data) setSelected(new Set(current.data.category_ids));
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

  const isLoading = categories.isLoading || current.isLoading;
  const selCount = selected.size;

  return (
    <div className="page narrow">
      <div className="interests-header">
        <h1>What do you want to learn?</h1>
        <p className="muted">
          Pick the topics that interest you — we'll fill your feed with posts
          from all of them. You can change this any time.
        </p>
        {selCount > 0 && (
          <p className="interests-count">
            {selCount} {selCount === 1 ? "category" : "categories"} selected
          </p>
        )}
      </div>

      {isLoading ? (
        <div className="muted">Loading…</div>
      ) : categories.data && categories.data.length > 0 ? (
        <div className="category-grid">
          {categories.data.map((cat: InterestCategory) => {
            const on = selected.has(cat.category_id);
            return (
              <button
                key={cat.category_id}
                className={`category-tile${on ? " on" : ""}`}
                onClick={() => toggle(cat.category_id)}
                aria-pressed={on}
              >
                <span className="category-emoji" aria-hidden="true">
                  {cat.emoji}
                </span>
                <span className="category-label">{cat.label}</span>
                <span className="category-desc muted">{cat.description}</span>
                {on && (
                  <span className="category-check" aria-hidden="true">✓</span>
                )}
              </button>
            );
          })}
        </div>
      ) : (
        <p className="muted">No categories available yet.</p>
      )}

      <div className="page-actions">
        <button
          className="primary"
          disabled={save.isPending || selCount === 0}
          onClick={() => save.mutate()}
        >
          {save.isPending
            ? "Saving…"
            : selCount === 0
            ? "Select at least one"
            : "Save & go to feed"}
        </button>
      </div>
    </div>
  );
}
