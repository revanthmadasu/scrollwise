"""Real-LLM evaluation of topic canonicalization (the dedup matcher).

Unlike tests/test_canonicalizer.py (which uses a fake LLM and runs in CI), this
hits the SAME LLM as production — it builds the client from your .env via
get_llm_client(), so on EC2 it uses Bedrock, locally it uses whatever
LLM_BACKEND points at. It therefore costs real tokens; run it by hand, not in CI.

What it checks: for each case you give an array of user prompts and the boolean
you expect:
  * expected = True  -> all prompts are the SAME topic, so they must canonicalize
                        to a single shared canonical_key.
  * expected = False -> at least one prompt is a DIFFERENT topic, so the keys
                        must NOT all collapse to one.
The actual result is `len(distinct canonical_keys) == 1`. A case passes when
actual == expected. This is exactly the equality the dedup lookup relies on.

Usage (from the app root, venv active):
    python -m scripts.eval_canonicalization
    python -m scripts.eval_canonicalization --cases my_cases.json

A --cases JSON file is a list of objects:
    [
      {"prompts": ["teach me about WWII", "the second world war"], "expected": true},
      {"prompts": ["roman empire", "the human immune system"],     "expected": false}
    ]

Exit code is 0 when every case passes, 1 otherwise (usable in a smoke check).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

from generators.canonicalizer import TopicCanonicalizer
from generators.llm_client import get_llm_client


@dataclass
class Case:
    prompts: list[str]
    expected: bool  # True = all the same topic; False = at least one differs


# Edit these, or pass --cases <file.json>. Each case: a list of user prompts and
# whether they all describe the same topic (True) or not (False).
DEFAULT_CASES: list[Case] = [
    # --- same topic -> expected True ---
    Case(["teach me about WWII", "the second world war"], True),
    Case(["I want to learn machine learning", "intro to ML basics", "machine learning"], True),
    Case(["the roman empire", "Tell me about Ancient Rome", "ROMAN EMPIRE!"], True),
    Case(["how do photosynthesis work", "explain photosynthesis to me"], True),
    # Censored / obfuscated spelling must collapse to the uncensored form.
    Case(
        [
            "The Subtle Art of Not Giving a F*ck",
            "The Subtle Art of Not Giving a Fuck",
            "the subtle art of not giving a f**k",
        ],
        True,
    ),
    # --- different topics -> expected False ---
    Case(["the roman empire", "the human immune system"], False),
    Case(["machine learning", "World War II", "photosynthesis"], False),
    Case(["World War I", "World War II"], False),

    # --- longer prompts, same topic -> expected True ---
    Case(
        [
            "I would like a structured, beginner-friendly introduction to the "
            "fundamentals of machine learning, covering what models are and how "
            "they are trained from data",
            "teach me the basics of machine learning, like how a model learns "
            "patterns from examples, explained simply for someone just starting out",
        ],
        True,
    ),
    Case(
        [
            "Can you walk me through, step by step, how photosynthesis works — "
            "how plants take in sunlight, water and carbon dioxide and turn it "
            "into energy and oxygen?",
            "explain the process of photosynthesis in plants and why it matters "
            "for life on earth",
        ],
        True,
    ),

    # --- broken / non-native English, same topic -> expected True ---
    Case(
        [
            "i am beginner, i want understand how the stock market is work and "
            "how to buy the share for make money",
            "please teach me basics of investing in stock market for totally "
            "beginner person who dont know anything about shares and trading",
            "introduction to stock market investing for beginners",
        ],
        True,
    ),
    Case(
        [
            "wat is ML and how it works, i dont have any background pls explain easy",
            "I would like a gentle introduction to the fundamentals of machine learning",
        ],
        True,
    ),
    Case(
        [
            "i not understand the neural network and the deep learning, i want "
            "learn from zero how the AI model is getting trained",
            "give me an introduction to how neural networks and deep learning work",
        ],
        True,
    ),

    # --- longer / broken English, different topics -> expected False ---
    Case(
        [
            "please explain to me how the french revolution did happen and why "
            "the people was so angry against the king and queen at that time",
            "i want to learn about quantum computing and what is the qubits and "
            "how they are different from normal computer bits",
        ],
        False,
    ),
    Case(
        [
            "teach me how to cook the authentic italian pasta from scratch, "
            "including how to make the tomato sauce by myself at home",
            "what are the rules of chess for a complete beginner who never "
            "play this game before in his life",
        ],
        False,
    ),
]

# ANSI colors (skipped automatically when stdout isn't a TTY).
_TTY = sys.stdout.isatty()
_GREEN = "\033[32m" if _TTY else ""
_RED = "\033[31m" if _TTY else ""
_DIM = "\033[2m" if _TTY else ""
_RESET = "\033[0m" if _TTY else ""


def _load_cases(path: str | None) -> list[Case]:
    if path is None:
        return DEFAULT_CASES
    try:
        with open(path) as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise SystemExit(
            f"--cases file not found: {path!r} (cwd: {os.getcwd()}). "
            "Use a path relative to where you're running, or an absolute path."
        )
    except json.JSONDecodeError as e:
        raise SystemExit(f"--cases file {path!r} is not valid JSON: {e}")
    if not isinstance(raw, list):
        raise SystemExit(
            f"--cases file {path!r} must be a JSON list of "
            '{"prompts": [...], "expected": bool} objects.'
        )
    cases: list[Case] = []
    for i, item in enumerate(raw):
        try:
            cases.append(Case(prompts=list(item["prompts"]), expected=bool(item["expected"])))
        except (KeyError, TypeError) as e:
            raise SystemExit(f"Bad case at index {i} in {path}: {e}")
    return cases


def run(cases: list[Case]) -> int:
    load_dotenv()
    llm = get_llm_client()
    canon = TopicCanonicalizer(llm)

    print(f"Canonicalization eval — LLM: {getattr(llm, 'model_version', 'unknown')}")
    print(f"{len(cases)} case(s)\n")

    failures = 0
    for idx, case in enumerate(cases, 1):
        # One real LLM call per prompt.
        results = [(p, *canon.canonicalize(p)) for p in case.prompts]
        keys = {key for (_p, _title, key) in results}
        actual = len(keys) == 1
        passed = actual == case.expected

        if passed:
            verdict = f"{_GREEN}PASS{_RESET}"
        else:
            verdict = f"{_RED}FAIL{_RESET}"
            failures += 1

        print(f"[{idx}] {verdict}  expected={case.expected}  actual={actual}  "
              f"({len(keys)} distinct key{'s' if len(keys) != 1 else ''})")
        for prompt, title, key in results:
            print(f"       {prompt!r:45} {_DIM}->{_RESET} title={title!r:30} key={key!r}")
        print()

    total = len(cases)
    summary = f"{total - failures}/{total} passed"
    if failures:
        print(f"{_RED}{summary}{_RESET}")
    else:
        print(f"{_GREEN}{summary}{_RESET}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-LLM canonicalization eval.")
    parser.add_argument(
        "--cases",
        help="Path to a JSON file of cases (list of {prompts:[...], expected:bool}). "
        "Defaults to the built-in DEFAULT_CASES.",
    )
    args = parser.parse_args()
    sys.exit(run(_load_cases(args.cases)))


if __name__ == "__main__":
    main()
