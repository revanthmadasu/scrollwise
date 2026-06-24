---
name: scrollwise-drain
description: >-
  Operate and troubleshoot the ScrollWise prod content-generator worker, the
  `scrollwise-drain` systemd service on EC2. Use this whenever the user mentions
  scrollwise-drain, the drain worker/poller, the prompt queue not generating,
  posts coming out image-based instead of template-based, "templates aren't
  showing up in prod", restarting/checking/tailing logs for the generator, or
  any prod issue where new ScrollWise posts aren't generating or aren't picking
  up newly approved templates. Reach for this skill even when the user doesn't
  name the service — "why is prod still making image posts" or "I approved
  templates but nothing changed" are the classic symptoms it solves.
---

# Operating `scrollwise-drain`

`scrollwise-drain` is the always-on **systemd service that runs the ScrollWise
content generator** on the prod EC2 box. It is the consumer half of the
prompt→generation loop: `apps/api` enqueues a row in the `user_prompts` table
when a user submits a topic; this worker polls that queue (default every 2s),
generates the curriculum + posts, writes them to Postgres, and flips the prompt
to `ready` (or `failed`).

- **Unit file:** `/etc/systemd/system/scrollwise-drain.service`
  (installed by `infra/ec2_drain_setup.sh`).
- **What it runs:**
  `services/content-generator/.venv/bin/python -m scripts.drain_prompts --interval 2 --batch-size 5`
- **Where:** prod EC2 (e.g. `ubuntu@…:/opt/ScrollWise`). Runs as the `ubuntu`
  user, `Restart=always`, starts on boot.
- **DB:** its `.env` sets `DB_BACKEND=postgres` + a local `content_generator`
  Postgres URL, `IMAGE_BACKEND=stub`, `LLM_BACKEND=bedrock`.

These commands must run **on the prod box** (SSH in first). Claude cannot reach
prod from a local session — give the user the command, or run it only if the
session is already on the box.

## Everyday operations

```bash
systemctl status scrollwise-drain          # running? since when? last exit?
journalctl -u scrollwise-drain -f          # live JSON logs (prompt_claimed/ready/failed)
journalctl -u scrollwise-drain -n 100 --no-pager   # recent history
sudo systemctl restart scrollwise-drain    # restart (see "the big gotcha")
sudo systemctl stop scrollwise-drain       # stop (won't restart until started)
sudo systemctl start scrollwise-drain
sudo systemctl disable --now scrollwise-drain   # stop + don't start on boot
```

The log lines are structured JSON. Useful events to grep for:
`drain_loop_start`, `prompt_claimed`, `prompt_ready`, `prompt_failed`,
`template_fill_failed`.

## The big gotcha: restart after approving or editing templates

**This is the #1 reason to use this skill.** The worker builds its `Pipeline`
**once at process startup** and loads the approved-template catalog right then
(`generators/pipeline.py`, `Pipeline.__init__` →
`repo.list_approved_templates()`). `run_forever()` then loops on that same
object forever and **never re-reads the catalog**.

Consequence: if you approve or change templates in the DB while the worker is
running, the running process keeps using its stale catalog. If the catalog was
empty at startup, `_select_template` returns `None` for every post, so every new
post is generated the **legacy image-based way** — even though the `templates`
table now has approved rows.

**Symptom → fix.** "I approved templates in prod but posts are still
image-based" (and the generator is on the right branch, and the posts are newly
generated):

```bash
sudo systemctl restart scrollwise-drain
systemctl is-active scrollwise-drain        # expect: active
```

After the restart, the fresh process reloads the approved catalog. **Newly
generated** posts will be templated and will skip image generation. Already-
generated image posts stay image-based — only new generation changes.

Remember this rule: **every time templates are approved/edited in prod, restart
`scrollwise-drain`.** It is not automatic.

## Diagnosing "prod is still making image-based posts"

Work down this list — the fix differs at each step. See
`references/troubleshooting.md` for the full decision tree and the exact SQL.

1. **Is the worker on the branch with template logic?** If the deployed code
   predates template selection (`generators/templating.py`,
   the template branch in `pipeline.py`), it can never templatize. Redeploy.
2. **Stale catalog?** Worker started before templates were approved → restart
   (see the gotcha above). This is the most common cause.
3. **Are the posts actually new?** Posts created before templates went live are
   permanently image-based. Check `created_at`.
4. **Same DB?** Confirm the worker's `DATABASE_URL` points at the same Postgres
   where templates were approved.
5. **Any approved rows at all?** `SELECT status, COUNT(*) FROM templates GROUP
   BY status;` — need rows with `status='approved'`.
6. **Silent catalog error?** `list_approved_templates()` swallows all
   exceptions and returns `[]`. Check the logs around `drain_loop_start`.

Quick check that templating is now working, after a prompt drains through:

```sql
SELECT template_id, COUNT(*) FROM posts
WHERE created_at > now() - interval '10 minutes'
GROUP BY template_id;
```

Newly generated rows should have a non-null `template_id`.

## How this relates to DB migrations

The generator and API own different tables, and migrations run differently:

- **API-owned tables** (`templates`, `users.is_admin`, etc.): managed by
  **Alembic**. `cd apps/api && alembic upgrade head`.
- **Contract tables** `posts` / `curricula` (generator-owned): Alembic
  **deliberately skips** them. Their columns (e.g. `posts.template_id`,
  `posts.template_inputs`) are added by the **generator's** additive migration
  in `Repository._run_migrations()`, applied by connecting the generator to the
  DB — run `python -m scripts.init_db` from `services/content-generator`
  (with `DB_BACKEND=postgres` + `DATABASE_URL` set).

So if `posts` is missing the template columns in prod, `alembic upgrade head`
will **not** fix it — run `init_db` (or just let the worker start, which also
runs the migration). See `references/troubleshooting.md`.

## Related infra scripts

- `infra/ec2_drain_setup.sh` — installs/reinstalls the service (also writes
  `.env`, sets up the venv).
- `infra/restart_prod.sh` — full public redeploy (API + web + Caddy + this
  worker). Restarts `scrollwise-drain` as its last step.
- `infra/healthcheck.sh` — health check for the drain service.
