# Troubleshooting `scrollwise-drain`

Full decision trees and exact commands. SKILL.md has the summary; come here for
the details.

## "Prod is still making image-based posts (not template-based)"

The generator falls back to legacy image rendering whenever it can't select a
template. Each cause below has a different fix — walk them in order, because a
later check is pointless if an earlier one is the real problem.

### 1. Is the deployed worker on the branch with template logic?

If the running code predates the template feature, there is no selection logic
at all and every post is image-based regardless of the DB.

```bash
cd /opt/ScrollWise && git rev-parse --abbrev-ref HEAD
ls services/content-generator/generators/templating.py   # exists on the template branch
grep -n "_select_template" services/content-generator/generators/pipeline.py
```

Fix: deploy the template branch, then restart (`sudo systemctl restart
scrollwise-drain`).

### 2. Stale in-memory catalog (most common)

The worker loads the approved-template catalog **once at startup**
(`Pipeline.__init__` → `list_approved_templates()`) and `run_forever()` reuses
that object forever. If templates were approved *after* the worker started, the
process is still using its old (often empty) catalog.

Check when the worker started vs. when templates were approved:

```bash
systemctl show scrollwise-drain -p ActiveEnterTimestamp
```

```sql
SELECT template_id, status, approved_at FROM templates
WHERE status='approved' ORDER BY approved_at DESC;
```

If `approved_at` is later than `ActiveEnterTimestamp`, that's the bug.

Fix:

```bash
sudo systemctl restart scrollwise-drain
systemctl is-active scrollwise-drain
```

### 3. Are the posts actually newly generated?

Posts generated before templates went live are permanently image-based; only
new generation is templated.

```sql
SELECT post_id, template_id, created_at FROM posts
ORDER BY created_at DESC LIMIT 20;
```

If the image-based posts are old and the newest ones have a `template_id`,
nothing is wrong — the feed just still contains old posts.

### 4. Same database?

The worker must read the same Postgres where templates were approved.

```bash
grep DATABASE_URL /opt/ScrollWise/services/content-generator/.env
```

Confirm host/db match the API's DB. (The generator uses a plain libpq URL:
`postgresql://…`, NOT the `postgresql+asyncpg://…` the API uses.)

### 5. Any approved rows at all?

```sql
SELECT status, COUNT(*) FROM templates GROUP BY status;
```

Need at least one `approved` row. Draft/in-review templates are ignored.

### 6. Silent catalog error

`Repository.list_approved_templates()` wraps its query in
`try/except: return []` — any error (missing column, permissions) silently
disables templating. Look at the logs right after a restart:

```bash
sudo systemctl restart scrollwise-drain
journalctl -u scrollwise-drain -n 50 --no-pager | grep -i "drain_loop_start\|error\|exception"
```

If you suspect this, run the same query the code runs, by hand, against prod:

```sql
SELECT template_id, name, vibe, compatible_content_types, fields, version
FROM templates WHERE status = 'approved';
```

An error here (e.g. a missing column) is the smoking gun → the API migrations
weren't fully applied (`cd apps/api && alembic upgrade head`).

### Confirm the fix

After a prompt drains through post-restart:

```sql
SELECT template_id, COUNT(*) FROM posts
WHERE created_at > now() - interval '10 minutes'
GROUP BY template_id;
```

Newly generated rows should carry a non-null `template_id`.

## "`posts` table is missing `template_id` / `template_inputs` in prod"

This is expected after only running Alembic. Alembic manages **API-owned**
tables and explicitly excludes the `posts`/`curricula` contract tables. Those
columns are added by the **generator's** additive migration in
`Repository._run_migrations()`.

Apply it by connecting the generator to prod (idempotent, additive — both
columns are nullable/defaulted, no table rewrite):

```bash
cd /opt/ScrollWise/services/content-generator
# uses .env if it already has DB_BACKEND=postgres + DATABASE_URL:
python -m scripts.init_db
# or explicitly:
DB_BACKEND=postgres DATABASE_URL='postgresql://USER:PASS@HOST:5432/DBNAME' \
  python -m scripts.init_db
```

Run scripts as **modules** (`python -m scripts.init_db`), not
`python scripts/init_db.py` — the latter puts `scripts/` on the path and fails
with `ModuleNotFoundError: No module named 'storage'`.

Equivalent manual SQL (what the code does):

```sql
ALTER TABLE posts ADD COLUMN IF NOT EXISTS template_id TEXT;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS template_inputs TEXT NOT NULL DEFAULT '{}';
```

Note: simply starting the worker also runs this migration (the `Repository`
constructor calls `_run_migrations()` on connect), so a restart can be enough.

## "The queue isn't draining / no posts are being generated"

```bash
systemctl status scrollwise-drain                 # active? crash-looping?
journalctl -u scrollwise-drain -n 100 --no-pager  # look for tracebacks
```

Common causes:

- **Waiting for the table.** On startup the worker waits (doesn't crash) until
  `apps/api` has created `user_prompts`. Log: "Waiting for user_prompts table".
  Start/verify the API.
- **Crash loop.** `Restart=always` + a real error (bad `.env`, DB unreachable,
  missing dep) shows as repeated restarts. Read the traceback in the logs.
- **Stuck prompts.** Rows orphaned in `generating` are auto-requeued to
  `pending` after `--stuck-after` seconds (default 900), but check:
  `SELECT status, COUNT(*) FROM user_prompts GROUP BY status;`
- **DB connectivity.** Confirm Postgres is up and `DATABASE_URL` in
  `services/content-generator/.env` is correct.

## Reinstalling the service

If the unit is missing or the command/flags need to change, reinstall:

```bash
cd /opt/ScrollWise && ./infra/ec2_drain_setup.sh
# tunables: DRAIN_INTERVAL=2 BATCH_SIZE=5 ./infra/ec2_drain_setup.sh
```

This rewrites `/etc/systemd/system/scrollwise-drain.service`, ensures the venv +
deps (including `psycopg2-binary`), writes `.env` if absent, then
`daemon-reload` + `enable` + `restart`.
