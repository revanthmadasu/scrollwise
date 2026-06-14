"""Backfill canonical_key for curricula created before topic dedup existed.

Legacy curricula have canonical_key = NULL and are therefore invisible to the
dedup lookup: a prompt for an already-existing topic generates a duplicate the
first time it's re-requested. This one-off backfill computes a key for those
rows so they become reuse candidates immediately.

Two key sources:
  * default: normalize(title) — free, deterministic, no LLM. Stored titles are
    already fairly clean, so this is usually enough.
  * --use-llm: run the full TopicCanonicalizer (same LLM as prod via .env),
    matching exactly how new prompts are canonicalized. Costs one LLM call per
    legacy row.

Writing goes through repo.save_curriculum(), so the canonical_key column AND the
stored `tree` JSON stay consistent, and the UNIQUE index still guards against
two legacy rows collapsing to the same key (the second is reported and skipped —
that's a genuine pre-existing duplicate to merge by hand later).

Usage (from the app root, venv active):
    python -m scripts.backfill_canonical_keys --dry-run        # preview only
    python -m scripts.backfill_canonical_keys                  # write, normalize()
    python -m scripts.backfill_canonical_keys --use-llm        # write, full LLM canonicalize

Safe to re-run: it only touches rows whose canonical_key is still NULL.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from generators.canonicalizer import TopicCanonicalizer, normalize
from generators.llm_client import get_llm_client
from storage.repository import CurriculumKeyConflict, Repository


def run(*, use_llm: bool, dry_run: bool) -> int:
    load_dotenv()
    repo = Repository()
    try:
        topic_ids = repo.curricula_missing_canonical_key()
        if not topic_ids:
            print("Nothing to backfill — every curriculum already has a canonical_key.")
            return 0

        canon = TopicCanonicalizer(get_llm_client()) if use_llm else None

        mode = "LLM canonicalize" if use_llm else "normalize(title)"
        action = "would set" if dry_run else "setting"
        print(f"{len(topic_ids)} curriculum(s) missing a canonical_key. "
              f"Key source: {mode}. {action.capitalize()} keys...\n")

        # Track keys in use so two rows mapping to the same key are caught even
        # in --dry-run. Seed with keys already persisted (e.g. from a prior
        # partial run) so the preview matches what a write would actually do.
        seen: dict[str, str] = repo.existing_canonical_keys()
        updated = skipped = 0

        for topic_id in topic_ids:
            curriculum = repo.load_curriculum(topic_id)
            if curriculum is None:
                continue  # vanished between the list and the load
            title = curriculum.title

            if use_llm:
                _canonical_title, key = canon.canonicalize(title)
            else:
                key = normalize(title)

            if not key:
                print(f"  SKIP  {topic_id!r}: title {title!r} normalized to an empty key")
                skipped += 1
                continue

            collide = seen.get(key)
            if collide is not None:
                print(f"  SKIP  {topic_id!r}: key {key!r} already taken by {collide!r} "
                      "(pre-existing duplicate topic)")
                skipped += 1
                continue

            print(f"  {'WOULD' if dry_run else 'OK   '} {topic_id!r:30} "
                  f"title={title!r:35} -> key={key!r}")

            if not dry_run:
                curriculum.canonical_key = key
                try:
                    repo.save_curriculum(curriculum)
                except CurriculumKeyConflict:
                    print(f"        ^ conflict: key {key!r} already exists in DB — skipped")
                    skipped += 1
                    continue
            seen[key] = topic_id
            updated += 1

        verb = "would update" if dry_run else "updated"
        print(f"\nDone. {verb} {updated}, skipped {skipped}.")
        if dry_run:
            print("Dry run — no changes written. Re-run without --dry-run to apply.")
        return 0
    finally:
        repo.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill canonical_key on legacy curricula."
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the full LLM canonicalizer (same backend as prod) instead of "
        "the free normalize(title) heuristic. Costs one LLM call per row.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing anything.",
    )
    args = parser.parse_args()
    sys.exit(run(use_llm=args.use_llm, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
