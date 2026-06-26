---
name: scrollwise-logging
description: >-
  How logging works across ScrollWise — the structured-JSON logger, log files,
  and where prod logs live. Use this whenever the user asks "do we have
  logging?", "where is the log file?", "how do I see the logs?", "tail the prod
  logs", wants to add or change a logger in a component, set a log level, point
  logs at a file, configure log rotation, or debug why a log file isn't being
  written. Covers both the content-generator (`generators/_logging.py`,
  `CONTENT_GEN_LOG_*`) and apps/api (`app/_logging.py`, `LOG_*` settings), plus
  the `infra/logs/*.log` convention wired up by the EC2 setup scripts. Reach for
  it even when the user doesn't say "logging" — "where does the drain write its
  output", "why is nothing in api.log", and "make the generator log to a file"
  are all this skill.
---

# Logging in ScrollWise

Every component logs **structured JSON, one object per line**, with the same
shape: `{"ts", "level", "msg", "logger", ...extra}`. The two Python services
share a near-identical logger module; `apps/web` (Vite) just emits its dev-server
output. In prod, all on-disk logs land in **`infra/logs/*.log`** next to each
other.

## The JSON logger (both Python services)

| Service | Module | Helper |
|---|---|---|
| content-generator | `services/content-generator/generators/_logging.py` | `get_logger(name)` |
| apps/api | `apps/api/app/_logging.py` | `get_logger(name)` + `configure_logging()` |

Both define the same `JsonFormatter`. Use the module logger — **never `print`**
(the content-generator CLAUDE.md mandates this):

```python
from generators._logging import get_logger   # content-generator
# from app._logging import get_logger         # apps/api
logger = get_logger(__name__)
logger.info("prompt_ready", extra={"prompt_id": pid, "topic_id": tid})
```

Anything in `extra=` is merged into the JSON object as top-level keys — that's
how events stay greppable (`prompt_claimed`, `prompt_ready`, `prompt_failed`,
`template_fill_failed`, `drain_loop_start`).

Logs always go to **stderr**, so journald / container drivers / shell redirects
capture them no matter what. A rotating **file** handler is *opt-in* via env.

## Configuration — env vars

The two services use different names because they read config differently
(content-generator reads `os.environ` after `load_dotenv()`; apps/api reads its
pydantic `Settings`, so the names are `Settings` field names).

| Knob | content-generator | apps/api |
|---|---|---|
| File path (enables file logging) | `CONTENT_GEN_LOG_FILE` | `LOG_FILE` |
| Rotation size (bytes) | `CONTENT_GEN_LOG_MAX_BYTES` (10 MB) | `LOG_MAX_BYTES` (10 MB) |
| Rotation backups | `CONTENT_GEN_LOG_BACKUP_COUNT` (5) | `LOG_BACKUP_COUNT` (5) |
| Level | `CONTENT_GEN_LOG_LEVEL` (INFO) | `LOG_LEVEL` (INFO) |

Unset the file var → **stderr only** (current default for local dev). Set it →
rotating `RotatingFileHandler` *plus* stderr. apps/api's vars are also documented
in `apps/api/.env.example`.

> Note: at `…LOG_LEVEL=DEBUG`, third-party libs (passlib, etc.) also emit debug
> lines, since the level is applied at the root logger in apps/api.

## Where the logs are in prod

All under **`infra/logs/`** on the EC2 box (alongside each other by design):

| File | Producer | How it gets there |
|---|---|---|
| `infra/logs/api.log` | apps/api (uvicorn) | whole-process stdout/stderr redirect |
| `infra/logs/web.log` | apps/web (Vite) | whole-process stdout/stderr redirect |
| `infra/logs/content-generator.log` | drain worker | rotating `CONTENT_GEN_LOG_FILE` |

- **api.log / web.log** come from `infra/ec2_app_setup.sh` (and
  `infra/restart_api.sh` / `infra/restart_web.sh`): the processes are started
  with `nohup … > infra/logs/api.log 2>&1` and a sibling `*.pid` file. These are
  **not** rotating — they grow until truncated/rotated externally.
- **content-generator.log** comes from `infra/ec2_drain_setup.sh`: the
  `scrollwise-drain` systemd unit sets
  `Environment=CONTENT_GEN_LOG_FILE=…/infra/logs/content-generator.log`, so the
  generator's own `RotatingFileHandler` writes it. The same JSON **also** goes to
  the **journal** (`journalctl -u scrollwise-drain`).

```bash
tail -f infra/logs/api.log
tail -f infra/logs/content-generator.log          # or: journalctl -u scrollwise-drain -f
grep prompt_failed infra/logs/content-generator.log | tail
```

These run **on the prod box** — SSH in first; Claude can't reach prod from a
local session.

## Adding logging to a component

1. `logger = get_logger(__name__)` at module top.
2. Log events as short snake_case `msg` strings + structured `extra=` fields.
3. For a **new entry point / script** in the content-generator, call
   `load_dotenv()` **before** importing any `generators.*` module — module-level
   loggers read `CONTENT_GEN_LOG_FILE` the first time they're created, so loading
   `.env` too late means the file handler never attaches. (`scripts/drain_prompts.py`
   is the reference for the correct order.)
4. In apps/api the file handlers are installed by `configure_logging()`, called
   once at the top of `app/main.py`. New routers/services just call `get_logger`.

## Pointing prod file logs somewhere else

- **Drain worker:** edit the `Environment=CONTENT_GEN_LOG_FILE=…` line in
  `/etc/systemd/system/scrollwise-drain.service` (or re-run
  `infra/ec2_drain_setup.sh`), then
  `sudo systemctl daemon-reload && sudo systemctl restart scrollwise-drain`.
- **API:** it currently relies on the shell redirect in `ec2_app_setup.sh` /
  `restart_api.sh` to `infra/logs/api.log`. To switch it to the rotating
  `LOG_FILE` handler instead, set `LOG_FILE` in `apps/api/.env` and drop the
  `> infra/logs/api.log 2>&1` redirect (otherwise you double-write).

## Gotchas

- **Nothing in the file?** The file var is unset, or (content-generator) `.env`
  was loaded after the logger was built — see step 3 above.
- **`datetime.utcnow()`** is used in the formatter; it's deprecated on 3.12+ but
  still works. Replace with `datetime.now(timezone.utc)` if you touch it.
- **api.log / web.log don't rotate** — they're raw redirects, not
  `RotatingFileHandler`. Only `content-generator.log` self-rotates.

## Related

- `infra/ec2_app_setup.sh`, `infra/ec2_drain_setup.sh` — wire up the prod log
  files.
- `infra/restart_api.sh`, `infra/restart_web.sh`, `infra/restart_prod.sh` —
  restart processes and re-point the redirects.
- `scrollwise-drain` skill — operating the drain worker (its log is
  `content-generator.log`).
