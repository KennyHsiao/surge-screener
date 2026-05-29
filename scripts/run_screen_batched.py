#!/usr/bin/env python3
"""Batch-run Stage 2 LLM scoring to spread calls and dodge rate limits.

Repeatedly invokes scripts/02_llm_score.py with --resume --limit N, sleeping
between batches, until every candidate is scored (or --max-batches is hit). Each
batch merges into --output and skips already-scored tickers, so it's safe to stop
and resume across sessions. Defaults to a cheap Layer-1 model (Sonnet) for the
wide breadth pass — Opus stays for the deeper Layer 2/3 scripts.

Example (score the whole sp1500 result in 25-name batches, 60s apart, on Sonnet):
    python scripts/run_screen_batched.py \
        --input filtered_universe_sp1500.json --batch-size 25 --sleep 60
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def _remaining(output: str):
    try:
        return json.load(open(output)).get("remaining_unscored")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Batched Stage-2 scoring (rate-limit friendly)")
    ap.add_argument("--input", required=True, help="filtered_universe*.json from Stage 1")
    ap.add_argument("--prompt", default="system_prompts/01_surge_screener_prompt.md")
    ap.add_argument("--output", default="scored_candidates.json")
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=60.0, help="seconds between batches")
    ap.add_argument("--provider", default="auto")
    ap.add_argument("--model", default="claude-opus-4-7", help="model for regime/depth")
    ap.add_argument("--layer1-model", default="claude-sonnet-4-6",
                    help="cheap model for the breadth pass (set '' to use --model)")
    ap.add_argument("--min-score", type=int, default=65)
    ap.add_argument("--max-batches", type=int, default=0, help="0 = until done")
    ap.add_argument("--case-library", default=None)
    args = ap.parse_args()

    score_py = str(Path(__file__).resolve().parent / "02_llm_score.py")
    batch = 0
    while True:
        batch += 1
        cmd = [sys.executable, score_py, "--input", args.input, "--prompt", args.prompt,
               "--output", args.output, "--resume", "--limit", str(args.batch_size),
               "--provider", args.provider, "--model", args.model,
               "--min-score", str(args.min_score)]
        if args.layer1_model:
            cmd += ["--layer1-model", args.layer1_model]
        if args.case_library:
            cmd += ["--case-library", args.case_library]

        print(f"\n=== Batch {batch} (size {args.batch_size}) ===", flush=True)
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            print(f"[batch] Stage 2 exited {rc}; stopping (rerun to resume).", file=sys.stderr)
            return rc

        rem = _remaining(args.output)
        print(f"[batch] remaining unscored: {rem}", flush=True)
        if rem is None:
            print("[batch] could not read remaining_unscored; stopping.", file=sys.stderr)
            return 1
        if rem <= 0:
            print(f"[batch] ✓ all candidates scored after {batch} batch(es).")
            return 0
        if args.max_batches and batch >= args.max_batches:
            print(f"[batch] hit --max-batches={args.max_batches}; {rem} still unscored "
                  "(rerun to continue).")
            return 0
        print(f"[batch] sleeping {args.sleep:.0f}s before next batch…", flush=True)
        time.sleep(args.sleep)


if __name__ == "__main__":
    sys.exit(main())
