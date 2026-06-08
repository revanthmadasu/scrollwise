import { useState } from "react";
import { api } from "../api/client";
import type { AnswerResult, Post } from "../api/types";

// Interactive test post. Submitting reveals correctness + explanation. A wrong
// answer tells the user the subtopic will resurface (remediation).
export function TestCard({ post }: { post: Post }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const options = post.options ?? [];

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
      <div className="test-tag">{post.blocking ? "Checkpoint · blocks progress" : "Quick check"}</div>
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
