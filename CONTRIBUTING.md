# Contributing to self-heal

Thanks for thinking about contributing. self-heal is a small library with a focused scope, and every improvement (bug fix, new proposer, benchmark run on a local model, a better example) genuinely helps.

This file is long on purpose. It tells you exactly what to set up, where the seams are, and how to get a PR merged without guessing.

## Ways to contribute

- **Try it and open a bug** if something fails. Traceback plus minimal repro is perfect.
- **Run the benchmark** against a local model (Qwen, Llama 3.3, DeepSeek, Codestral) and report numbers. See [issue #1](https://github.com/Johin2/self-heal/issues/1).
- **Add integration examples** for your favorite agent framework (CrewAI, AutoGen, Pydantic-AI, Strands).
- **Pick up a good first issue.** All issues tagged `good first issue` are kept scoped so a new contributor can finish in a weekend: [good first issues](https://github.com/Johin2/self-heal/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22).
- **Build a feature on the roadmap** (see README roadmap or the `enhancement` issue label).
- **Improve docs.** README sections, docstrings, examples.

If you're not sure where to start, open a discussion in an issue before writing code. Beats writing a PR that has to be re-scoped.

## Development setup

### Prerequisites

- Python 3.10 or newer (3.10 to 3.13 are CI-tested).
- Git.
- An API key for at least one LLM provider if you want to run live examples: Anthropic, OpenAI, Google AI Studio (Gemini), or anything LiteLLM supports.

### Clone and install

```bash
git clone https://github.com/Johin2/self-heal.git
cd self-heal

# Create a virtualenv
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
pip install -e ".[dev]"

# Windows (bash / Git Bash)
.venv/Scripts/pip install -e ".[dev]"

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `ruff`, and every optional LLM SDK so you can run the full test matrix locally.

### API keys for live examples

Unit tests are fully mocked and do not need any API key. If you want to run `examples/` or the benchmark, set one of:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-proj-...
export GEMINI_API_KEY=...
```

Never commit API keys. `.env` is already in `.gitignore`; prefer shell env vars for local use.

## Everyday commands

Run these from the repo root.

```bash
# Tests (fast, mocked, no network)
pytest

# Lint
ruff check .
ruff check --fix .              # auto-fix where possible

# Benchmark with whichever provider you have a key for
self-heal bench --proposer gemini --model gemini-2.5-flash
self-heal bench --proposer openai --model gpt-5
self-heal bench --proposer openai --model llama3.3 \
  --base_url http://localhost:11434/v1   # Ollama

# Build the distribution (sanity check before a release PR)
python -m build
twine check dist/*

# Regenerate the demo GIF
python scripts/make_demo_gif.py assets/demo.gif
```

CI runs `ruff check .` and `pytest` on Python 3.10, 3.11, 3.12, and 3.13. If both pass locally on your Python version, CI will usually be green.

**Note for contributors on Windows:** run `rm -rf .ruff_cache` before your final `ruff check .` if you've been iterating on files. A stale cache occasionally hides rules that CI catches.

## Project layout

```
self-heal/
├── src/self_heal/
│   ├── __init__.py         # Public exports; lazy-loads optional proposers
│   ├── core.py             # @repair decorator
│   ├── loop.py             # RepairLoop (sync + async runners, cache, safety, events)
│   ├── diagnose.py         # Failure classification
│   ├── propose.py          # Prompt building, history formatting, code extraction
│   ├── verify.py           # Verifiers and test-driven checks
│   ├── types.py            # Pydantic models (Failure, RepairAttempt, RepairResult)
│   ├── cache.py            # SQLite repair cache
│   ├── safety.py           # AST-based safety rails
│   ├── events.py           # RepairEvent and on_event callback
│   ├── pytest_plugin.py    # pytest --heal plugin
│   ├── cli.py              # self-heal CLI
│   └── llm/
│       ├── __init__.py     # LLMProposer Protocol + lazy exports
│       ├── _claude.py      # ClaudeProposer (requires anthropic)
│       ├── _openai.py      # OpenAIProposer (requires openai)
│       ├── _gemini.py      # GeminiProposer (requires google-genai)
│       └── _litellm.py     # LiteLLMProposer (requires litellm)
├── tests/
│   ├── test_core.py           # Loop + decorator smoke tests
│   ├── test_proposers.py      # Mocked tests for all four adapters
│   ├── test_v01_features.py   # Verifiers, tests, history, async
│   └── test_v02_features.py   # Cache, safety, events
├── benchmarks/
│   ├── tasks.py            # 19 curated buggy-function tasks
│   └── run.py              # Harness: naive vs self-heal comparison
├── examples/               # Integration patterns and single-file demos
├── scripts/
│   └── make_demo_gif.py    # Renders assets/demo.gif via Pillow
└── demo/                   # Minimal repro used to record the demo GIF
```

## Extending self-heal

This is where most contributions go. Four high-leverage extension points:

### 1. Add a new LLM proposer

Anything that turns a `(system, user)` prompt pair into a string can be a proposer.

Create `src/self_heal/llm/_myprovider.py`:

```python
"""MyProvider proposer."""

from __future__ import annotations

import os

try:
    from myprovider import Client
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "MyProviderProposer requires the `myprovider` package. "
        "Install with: pip install 'self-heal-llm[myprovider]'"
    ) from _err


class MyProviderProposer:
    """MyProvider-backed proposer."""

    def __init__(self, model: str, api_key: str | None = None):
        self.model = model
        self.client = Client(api_key=api_key or os.environ.get("MYPROVIDER_API_KEY"))

    def propose(self, system: str, user: str) -> str:
        response = self.client.generate(
            model=self.model,
            system=system,
            prompt=user,
        )
        return response.text or ""
```

Register it in `src/self_heal/llm/__init__.py`:

```python
def __getattr__(name: str):
    ...
    if name == "MyProviderProposer":
        from self_heal.llm._myprovider import MyProviderProposer
        return MyProviderProposer
    ...


__all__ = [
    ...,
    "MyProviderProposer",
]
```

Add an optional dependency in `pyproject.toml`:

```toml
[project.optional-dependencies]
myprovider = ["myprovider>=X.Y"]
```

Add a mocked test in `tests/test_proposers.py` following the `test_claude_proposer_returns_text_from_first_block` pattern. Patch the SDK, assert the proposer calls it with the right arguments, verify return value.

### 2. Add a safety rule

Safety rules live in `src/self_heal/safety.py`. Each rule is a check inside `_inspect_node` that yields a human-readable issue string. To add one:

```python
# In _inspect_node:
if isinstance(node, ast.Call) and _call_name(node.func) == "my_forbidden_fn":
    yield "call to `my_forbidden_fn` is not allowed"
```

Add a test in `tests/test_v02_features.py` that expects `UnsafeProposalError` for the new pattern.

### 3. Add an event type

Events live in `src/self_heal/events.py`. Add the literal to `EventType` and emit it from the right place in `loop.py`:

```python
# events.py
EventType = Literal[
    ...,
    "my_new_event",
]

# loop.py (wherever the moment happens):
emit(self.on_event, RepairEvent("my_new_event", attempt_number=n, extra={"foo": "bar"}))
```

Test with a capturing callback.

### 4. Add a benchmark task

In `benchmarks/tasks.py`, add a buggy source and matching tests:

```python
_my_task_buggy = """
def my_func(x):
    # Deliberately wrong in a plausible way
    return x
"""


def _mt_simple(fn):
    assert fn(5) == 10


def _mt_edge(fn):
    assert fn(-1) == -2


TASKS.append(
    Task(
        name="my_task",
        description="What this function should do",
        buggy_source=_my_task_buggy,
        function_name="my_func",
        tests=[_mt_simple, _mt_edge],
    )
)
```

Good benchmark tasks share a pattern: the buggy version handles one case correctly but fails on a nearby edge case. That's where self-heal's multi-turn memory earns its keep.

## Testing guidelines

- **No live API calls in unit tests.** Use `ScriptedProposer` (see `tests/test_core.py`) or `unittest.mock.patch`.
- **Cover the new path end-to-end.** A PR that adds a feature without a test will bounce.
- **Windows SQLite gotcha.** If you write tests using `RepairCache`, use pytest's `tmp_path` fixture and call `cache.close()` at the end. `tempfile.TemporaryDirectory` can fail to clean up on Windows because SQLite still holds the file open.
- **Prefer deterministic tests.** If randomness is needed, seed it.

### Running a subset

```bash
pytest tests/test_v02_features.py -v
pytest -k "cache"
pytest -x                    # stop on first failure
pytest --lf                  # re-run only last-failed
```

## Code style

- **Formatter / linter:** `ruff` is the only tool. Its config is in `pyproject.toml`.
- **Line length:** 100 characters (enforced loosely; `E501` is in the ignore list).
- **Type hints:** required on public APIs. Internal helpers can skip them when obvious.
- **Docstrings:** required on public functions and classes. One line summary; expand only if the WHY is non-obvious.
- **Comments:** don't narrate code that identifiers already explain. Use comments only for non-obvious constraints, subtle invariants, or workaround context.
- **No em dashes** in docs, README, or release notes (personal project convention). Use commas, periods, or parentheses.

Run `ruff check --fix .` before opening a PR. It auto-sorts imports and applies most style fixes.

## Commit and PR process

### Branches

- Feature branches off `main`.
- Name them descriptively: `feat/streaming-events`, `fix/cli-monkey-patch`, `docs/contributing`, `bench/quixbugs`.

### Commit messages

- Short imperative subject line (under 72 characters).
- Optional body explaining the "why" behind the change.
- Reference issue numbers when relevant: `Closes #3`.
- Do not include `Co-Authored-By` lines.
- Atomic commits are welcome. Squash is fine at merge time.

Example:

```
feat(proposers): add Gemini-native async apropose

Implements apropose() on GeminiProposer using google.genai.Client.aio.
RepairLoop.arun picks this up automatically. Closes #4.
```

### Pull request checklist

Before marking a PR ready for review:

- [ ] `ruff check .` passes locally
- [ ] `pytest` passes locally
- [ ] New behavior has a test (mocked, no network)
- [ ] Docs / README updated if public API changed
- [ ] PR description names the issue it closes (if any) and summarizes the user-visible change
- [ ] No API keys, local paths, or personal data in the diff

CI runs lint and tests on all four supported Python versions. If CI is red, the PR won't merge.

### Review timeline

This is a solo-maintained project. Reviews usually happen within a few days. If a week passes with no response, ping the PR. It isn't personal.

### Release process (for maintainers)

Patch releases (`0.x.Y`) for bug fixes, minor releases (`0.X.0`) for new features. Release cuts:

1. Bump version in `pyproject.toml` and `src/self_heal/__init__.py`.
2. Confirm `ruff check .`, `pytest`, `python -m build`, and `twine check dist/*` all clean.
3. Commit and push.
4. `gh release create vX.Y.Z --title "..." --notes "..."` triggers the publish workflow, which uploads to PyPI via OIDC.

## Reporting bugs

1. Minimal repro (function source + how you invoked it + full traceback).
2. Python version, OS, self-heal version.
3. Which proposer / model was configured.
4. Expected vs actual.

Open a GitHub issue with that detail. The bug template (if present) will guide you.

## Reporting security issues

Do **not** open a public issue. Email the maintainer at the address in `pyproject.toml` with:

- The vulnerability description.
- Steps to reproduce.
- Potential impact.
- A suggested fix if you have one.

Expect an acknowledgement within 48 hours. Fixes will be coordinated with a patch release.

Known trust boundary: self-heal executes LLM-generated code via `exec()` inside the calling process. AST safety rails mitigate the obvious escape hatches, but the hard boundary is a process-level sandbox (tracked in [issue #7](https://github.com/Johin2/self-heal/issues/7)). Anything outside that well-understood boundary qualifies as a security issue.

## Communication

- **Bug reports, feature requests, questions about contributing:** GitHub Issues.
- **Design discussions for large features:** open a draft issue, wait for a response before writing code.
- **Quick questions:** a short comment on the relevant issue is fine.

## License

self-heal is released under the MIT License. By contributing, you agree that your contributions are licensed under the same terms.

Thanks for being here. Small PRs are welcome. Large PRs work best after a short design sketch in an issue.
