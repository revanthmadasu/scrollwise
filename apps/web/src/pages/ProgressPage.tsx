import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function ProgressPage() {
  const { data, isLoading } = useQuery({ queryKey: ["progress"], queryFn: api.progress });

  if (isLoading) return <div className="center muted">Loading…</div>;
  if (!data) return <div className="center error">Couldn't load progress.</div>;

  return (
    <div className="page narrow">
      <h1>Your progress</h1>

      <div className="stat-row">
        <div className="stat">
          <div className="stat-num">{data.tests_passed}</div>
          <div className="muted">tests passed</div>
        </div>
        <div className="stat">
          <div className="stat-num">{data.tests_taken}</div>
          <div className="muted">tests taken</div>
        </div>
        <div className="stat">
          <div className="stat-num">{data.topics.length}</div>
          <div className="muted">topics in progress</div>
        </div>
      </div>

      <h2 className="section">Topics</h2>
      {data.topics.length === 0 ? (
        <p className="muted">Nothing started yet. Head to your feed to begin.</p>
      ) : (
        <ul className="progress-list">
          {data.topics.map((t) => {
            const pct = t.total_posts ? Math.round((t.posts_seen / t.total_posts) * 100) : 0;
            return (
              <li key={t.topic_id} className="progress-row">
                <div className="progress-head">
                  <span className="topic-title">{t.topic_id}</span>
                  <span className="muted small">
                    {t.posts_seen}/{t.total_posts}
                  </span>
                </div>
                <div className="bar">
                  <div className="bar-fill" style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
