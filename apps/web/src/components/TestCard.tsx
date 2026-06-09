import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AnswerResult, Post } from "../api/types";

// Interactive test post. Submitting reveals correctness + explanation. A wrong
// answer tells the user the subtopic will resurface (remediation).
export function TestCard({ post }: { post: Post }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const options = post.options ?? [];

  // Lazily fetch the material this test covers, only when the user asks to revise.
  const revise = useQuery({
    queryKey: ["revise", post.post_id],
    queryFn: () => api.revise(post.post_id),
    enabled: showRevise,
  });

  async function submit() {
    if (selected === null || busy) return;
    setBusy(true);
    try {
      setResult(await api.answer(post.post_id, selected));
    } finally {
      setBusy(false);
    }
  }

  const answered = result !== null;

  return (
    <div className="test">
      <div className="test-head">
        <span className="test-tag">{post.blocking ? "Checkpoint · blocks progress" : "Quick check"}</span>
        <button className="revise-btn" onClick={() => setShowRevise((s) => !s)}>
          {showRevise ? "Hide revision" : "Revise"}
        </button>
      </div>

      {post.blocking && (
        <p className="test-gate-note muted">
          Pass this to unlock more posts in this topic.
        </p>
      )}

      {showRevise && (
        <div className="revise-panel">
          {revise.isLoading ? (
            <p className="muted">Loading the material…</p>
          ) : revise.data && revise.data.length > 0 ? (
            revise.data.map((p) => (
              <div key={p.post_id} className="revise-item">
                <h4>{p.title}</h4>
                <p>{p.body}</p>
              </div>
            ))
          ) : (
            <p className="muted">No earlier material found for this check.</p>
          )}
        </div>
      )}

      <h2 className="test-q">{post.question ?? post.title}</h2>
      <div className="options">
        {options.map((opt, i) => {
          let cls = "option";
          if (answered) {
            if (i === result!.correct_index) cls += " correct";
            else if (i === selected) cls += " wrong";
          } else if (i === selected) {
            cls += " selected";
          }
          return (
            <button
              key={i}
              className={cls}
              disabled={answered}
              onClick={() => setSelected(i)}
            >
              {opt}
            </button>
          );
        })}
      </div>

      {!answered ? (
        <button className="primary submit" disabled={selected === null || busy} onClick={submit}>
          {busy ? "Checking…" : "Submit answer"}
        </button>
      ) : (
        <div className={`verdict ${result!.is_correct ? "ok" : "bad"}`}>
          <strong>{result!.is_correct ? "Correct!" : "Not quite."}</strong>
          {result!.explanation && <p>{result!.explanation}</p>}
          {result!.remediation_queued && (
            <p className="muted">We'll revisit this topic in your feed to help it stick.</p>
          )}
        </div>
      )}
    </div>
  );
}
