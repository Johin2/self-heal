"""Sweep multiple local models against the self-heal benchmark.

Targets any OpenAI-compatible endpoint (Ollama, vLLM, llama.cpp server,
LM Studio). For each model it runs the benchmark, captures the
pass rates, and prints a Markdown-ready summary row.

Usage:
    python benchmarks/run_local_sweep.py \
        --models "qwen2.5-coder:14b,llama3.3:70b,deepseek-coder-v2:16b" \
        --base-url http://localhost:11434/v1

Then paste the printed rows into `benchmarks/RESULTS.md`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Match lines like "Naive single-shot: 13/19  (68%)" and
# "self-heal full:    19/19  (100%)".
_NAIVE_RE = re.compile(r"Naive single-shot:\s+(\d+)/(\d+)\s+\((\d+)%\)")
_SH_RE = re.compile(r"self-heal full:\s+(\d+)/(\d+)\s+\((\d+)%\)")


def run_one(
    model: str, base_url: str, attempts: int, suite: str, api_key: str,
) -> str:
    """Invoke benchmarks/run.py for a single model and return its stdout."""
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = api_key
    env["OPENAI_BASE_URL"] = base_url

    cmd = [
        sys.executable,
        str(REPO_ROOT / "benchmarks" / "run.py"),
        "--proposer", "openai",
        "--model", model,
        "--attempts", str(attempts),
    ]
    if suite != "default":
        cmd += ["--suite", suite]

    print(f"\n=== {model} ===", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    elapsed = time.time() - t0
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
    return proc.stdout + f"\n(elapsed: {elapsed:.0f}s)"


def parse_pass_rates(output: str) -> tuple[str, str]:
    naive = _NAIVE_RE.search(output)
    sh = _SH_RE.search(output)
    naive_str = f"{naive.group(1)}/{naive.group(2)} ({naive.group(3)}%)" if naive else "?"
    sh_str = f"{sh.group(1)}/{sh.group(2)} ({sh.group(3)}%)" if sh else "?"
    return naive_str, sh_str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        required=True,
        help="comma-separated list of model IDs to test",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434/v1",
        help="OpenAI-compatible endpoint (default: Ollama on localhost)",
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--suite", default="default", choices=["default", "quixbugs"]
    )
    parser.add_argument(
        "--api-key",
        default="ollama",
        help="passed as OPENAI_API_KEY (most local servers don't verify)",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("no models provided", file=sys.stderr)
        return 2

    rows: list[str] = []
    for model in models:
        output = run_one(model, args.base_url, args.attempts, args.suite, args.api_key)
        naive, sh = parse_pass_rates(output)
        rows.append(
            f"| openai (local) | {model} | {args.attempts} | "
            f"{naive} | {sh} | _your GPU_ | _you_ |"
        )

    print("\n\n=== Markdown rows for RESULTS.md ===\n")
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
