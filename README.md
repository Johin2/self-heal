# self-heal

[![CI](https://github.com/Johin2/self-heal/actions/workflows/ci.yml/badge.svg)](https://github.com/Johin2/self-heal/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/self-heal-llm.svg)](https://pypi.org/project/self-heal-llm/)
[![Python](https://img.shields.io/pypi/pyversions/self-heal-llm.svg)](https://pypi.org/project/self-heal-llm/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Automatic repair for failing Python code, powered by any LLM.

![self-heal demo](assets/demo.gif)

`self-heal` catches failures, proposes an LLM-guided fix with memory of prior attempts, verifies it, and retries. Works with Claude, OpenAI, Gemini, and 100+ other providers. Sync and async. One decorator.

```python
from self_heal import repair

def test_dollars(fn): assert fn("$12.99") == 12.99
def test_rupees(fn):  assert fn("₹1,299") == 1299.0
def test_euros(fn):   assert fn("€5,49") == 5.49

@repair(tests=[test_dollars, test_rupees, test_euros])
def extract_price(text: str) -> float:
    # Naive: only handles "$X.YY" with no commas
    return float(text.replace("$", ""))

extract_price("$12.99")   # triggers repair loop until ALL tests pass
```

## Benchmark

Two suites, both run against Gemini 2.5 Flash, 3 max attempts, v0.4 harness.

**Default suite** (19 hand-written bugs: price parsing, palindrome, flatten, roman numerals, camelCase-to-snake_case, Levenshtein, anagram, duration formatting, ...)

| Strategy | Tasks passed | Success rate | LLM calls |
|---|---:|---:|---:|
| Naive single-shot repair | 16 / 19 | 84% | 17 |
| **self-heal (multi-turn + memory)** | **18 / 19** | **95%** | 21 |

**QuixBugs** (31 classic one-line bugs; 9 graph/tree programs skipped by the loader for custom-deserialization reasons)

| Strategy | Tasks passed | Success rate | LLM calls |
|---|---:|---:|---:|
| Naive single-shot repair | 27 / 31 | 87% | 30 |
| **self-heal (multi-turn + memory)** | **29 / 31** | **94%** | 35 |

Reproduce: `self-heal bench --proposer gemini --model gemini-2.5-flash` (default) or `--suite quixbugs`. Full numbers, historical rows, and how to contribute your own in [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md). Task source in [`benchmarks/tasks.py`](benchmarks/tasks.py).

The +2 tasks on each suite share a pattern: the first proposed fix handles one edge case but misses another. Memory of the failed attempt plus test feedback lets the second proposal cover both. Roughly 20% more LLM calls for the additional wins. As frontier models keep improving the naive floor rises and this delta compresses; earlier runs against Gemini 2.5 Flash had naive at 68% instead of 84%, which is honest signal not cherry-picked.

## Install

`self-heal` ships with a Protocol and several optional adapters. Install the adapter(s) you want:

```bash
pip install 'self-heal-llm[claude]'    # Anthropic Claude (default)
pip install 'self-heal-llm[openai]'    # OpenAI + OpenAI-compatible endpoints
pip install 'self-heal-llm[gemini]'    # Google Gemini
pip install 'self-heal-llm[litellm]'   # 100+ providers via LiteLLM
pip install 'self-heal-llm[all]'       # everything
```

> PyPI distribution name is `self-heal-llm` (the short name `self-heal` was blocked by PyPI's similarity check with an unrelated package). The Python import stays `from self_heal import ...`.

## Provider support

| Adapter | Covers |
|---|---|
| `ClaudeProposer` | Anthropic Claude (native SDK) |
| `OpenAIProposer` | OpenAI + **any OpenAI-compatible endpoint** (OpenRouter, Together, Groq, Fireworks, Anyscale, Perplexity, xAI, DeepSeek, Azure, Ollama, LM Studio, vLLM, llama.cpp server, ...) |
| `GeminiProposer` | Google Gemini (native SDK) |
| `LiteLLMProposer` | 100+ providers via LiteLLM (Bedrock, Vertex, Cohere, Mistral, ...) |

## Features

### Multi-turn repair with memory
Every proposal sees the history of *prior failed attempts* so the LLM can't repeat the same mistake. This is the single biggest quality win over naive retry.

### Verifiers: `verify=callable`
Catch bad *return values*, not just exceptions:

```python
@repair(verify=lambda v: isinstance(v, float) and v > 0)
def extract_price(text): ...
```

If the predicate returns `False` or raises, self-heal treats it as a failure and repairs.

### Test-driven repair: `tests=[...]`
Give self-heal a test suite; it repairs until every test passes:

```python
def test_empty(fn):  assert fn("") is None
def test_dollar(fn): assert fn("$12.99") == 12.99

@repair(tests=[test_empty, test_dollar])
def extract_price(text): ...
```

### Async-native
The decorator auto-detects `async def` and awaits correctly; the LLM call runs in a thread pool so your event loop stays free.

```python
@repair()
async def fetch_and_parse(url: str) -> dict: ...
```

### Prompt customization: `prompt_extra="..."`
Append domain-specific instructions to every repair prompt. Useful for "always handle None inputs" or "use only the standard library."

### Bring your own LLM
Implement the `LLMProposer` Protocol (`def propose(self, system: str, user: str) -> str`) and pass it in.

### Repair cache: skip the LLM when you've seen it before
```python
from self_heal import repair

@repair(cache_path=".self_heal_cache.db")
def my_fn(...): ...
```
First repair hits the LLM. Subsequent identical failures are served from SQLite (zero latency, zero cost). Keyed on source hash + failure signature with whitespace and memory-address normalization.

### Safety: AST rails + subprocess sandbox
Two independent layers. Combine them freely.

```python
from self_heal import repair, SafetyConfig

# AST rails only (zero overhead)
@repair(safety="moderate")   # "moderate" | "strict" | SafetyConfig(...)
def my_fn(...): ...

# AST rails + process isolation (each call runs in `python -I`)
@repair(safety=SafetyConfig(level="moderate", sandbox="subprocess"))
def my_fn(...): ...
```
`moderate` rejects proposals that call `eval` / `exec` / `os.system`, import `subprocess` / `socket` / `pickle` / `ctypes`, or touch `__globals__` / `__class__` / other escape hatches. `strict` additionally forbids any non-whitelisted import. The subprocess sandbox adds a real process boundary: args and return values are pickled over stdin/stdout, and the child inherits none of the caller's globals (proposals must be self-contained). See [Safety](#safety) for the full trust model.

> **Sandbox + imports.** When `sandbox="subprocess"` is active, the child runs with `python -I` in a fresh namespace. **The repaired function must import every module it uses at the top of the definition.** `import math` at the caller module scope does NOT reach the sandbox, so a proposal that references `math.sqrt` without a local `import math` raises `NameError` on the first call. `self-heal` already hints at this in the LLM prompt when sandbox is active, but if you're writing a proposer by hand the same rule applies.

### Progress callbacks
```python
from self_heal import repair, RepairEvent

def watch(event: RepairEvent):
    print(event.type, event.attempt_number)

@repair(on_event=watch)
def my_fn(...): ...
```
Hooks fire on attempt start, failure, propose start/complete, install, cache hit/miss, safety violation, verify, and repair completion. Perfect for agent UIs and observability pipelines.

### Token streaming
When a callback is registered, self-heal streams LLM tokens through `propose_chunk` events as they arrive:

```python
from self_heal import RepairEvent, repair

def on_event(event: RepairEvent):
    if event.type == "propose_chunk":
        print(event.delta, end="", flush=True)

@repair(on_event=on_event)
def my_fn(...): ...
```
All four built-in proposers stream natively via their SDKs. Custom proposers can implement `propose_stream(system, user) -> Iterator[str]` (and `apropose_stream` for async) to participate; those without streaming fall back to a single completion. See [`examples/streaming_progress.py`](examples/streaming_progress.py).

### Native async proposers
`arun` prefers each SDK's native async client when the proposer provides `apropose`, falling back to `asyncio.to_thread(propose)` otherwise. All four built-in adapters ship with native async; custom proposers work either way.

### pytest plugin: `pytest --heal`
Mark any test with `@pytest.mark.heal(target="mymod.my_fn")`. When it fails with `--heal`, self-heal loads the target, repairs it using the test as verification, and prints the proposed diff at the end of the session.

```python
import pytest
from mymod import extract_price

@pytest.mark.heal(target="mymod.extract_price")
def test_rupees():
    assert extract_price("₹1,299") == 1299.0
```
```bash
pytest --heal              # print proposed fix, leave files untouched
pytest --heal-apply        # write the fix back to disk (creates a .py.heal-backup)
pytest --heal-apply-force  # also allow modification of git-dirty files
```
`--heal-apply` uses libcst for AST-faithful replacement when installed, falling back to textual replacement. It refuses to modify files with uncommitted git changes unless `--heal-apply-force` is given.

### CLI: heal a function from the command line
```bash
self-heal heal mymod.py::extract_price \
    --test tests/test_mymod.py::test_rupees \
    --apply
```
Loads the function, runs self-heal with your pytest-style test as verification, prints a unified diff, and (with `--apply`) writes the fix back to the file.

## Why this exists

AI coding agents fail on a lot of real tasks. The industry's current answer is "retry and hope." That's not a strategy.

`self-heal` treats repair as a first-class primitive: diagnose the failure, propose a targeted fix with memory of prior attempts, verify, retry. A thin library you can wrap around any Python function or agent tool.

## How it works

1. **Catch** the exception (or verifier/test failure) and capture inputs, traceback, failure type.
2. **Classify** the failure (exception, verifier, test, assertion, validation).
3. **Propose** a repaired function via an LLM with a failure-aware prompt that includes the full history of prior failed proposals.
4. **Recompile** the proposed function into the running process.
5. **Verify** with user-provided verifier + tests.
6. **Retry** with the same inputs until success or `max_attempts` exhausted.

## API

```python
from self_heal import repair

@repair(
    max_attempts=3,
    model="claude-sonnet-4-6",
    proposer=None,               # or ClaudeProposer / OpenAIProposer / ...
    verbose=False,
    on_failure="raise",          # or "return_none"
    verify=None,                 # Callable[[Any], bool]; raise or False triggers repair
    tests=None,                  # list[Callable[[Callable], Any]]
    prompt_extra=None,           # str; extra user instructions in every prompt
)
def my_fn(...): ...

my_fn.last_repair   # RepairResult with full attempt history
my_fn.repair_loop   # the underlying RepairLoop
```

For advanced use:

```python
from self_heal import RepairLoop

loop = RepairLoop(max_attempts=5, verbose=True)
result = loop.run(my_fn, args=(...), verify=..., tests=[...])

# Async:
result = await loop.arun(my_async_fn, args=(...))
```

## Using different providers

**Claude (default):**
```python
@repair()
def my_fn(...): ...
```

**OpenAI:**
```python
from self_heal.llm import OpenAIProposer

@repair(proposer=OpenAIProposer(model="gpt-5"))
def my_fn(...): ...
```

**Gemini:**
```python
from self_heal.llm import GeminiProposer

@repair(proposer=GeminiProposer(model="gemini-2.5-pro"))
def my_fn(...): ...
```

**Any OpenAI-compatible endpoint (OpenRouter, Groq, Ollama, ...):**
```python
from self_heal.llm import OpenAIProposer

# OpenRouter: hundreds of models through one key
OpenAIProposer(
    model="google/gemini-2.5-pro",
    base_url="https://openrouter.ai/api/v1",
)

# Local Ollama
OpenAIProposer(
    model="llama3.3",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
```

**LiteLLM catch-all (100+ providers):**
```python
from self_heal.llm import LiteLLMProposer

LiteLLMProposer(model="bedrock/anthropic.claude-3-5-sonnet")
LiteLLMProposer(model="vertex_ai/gemini-2.5-pro")
LiteLLMProposer(model="cohere/command-r-plus")
```

## Agent framework integration

`self-heal` composes with any Python agent framework. For Claude Agent SDK there's a first-class integration (one decorator instead of two); for everything else, wrap the tool's underlying callable with `@repair` and register the result as usual.

### Claude Agent SDK (first-class)

```python
from self_heal.integrations.claude_agent_sdk import healing_tool

@healing_tool(
    "price_from_text",
    "Extract a price from messy text.",
    {"text": str},
    verify=lambda r: isinstance(r, dict) and not r.get("is_error"),
)
async def price_from_text(args):
    text = args["text"]
    return {"content": [{"type": "text", "text": str(float(text.replace("$", "")))}]}
```

`healing_tool` takes both the Claude Agent SDK's `@tool` parameters and all of `@repair`'s parameters. The result is an `SdkMcpTool` ready to register with `create_sdk_mcp_server(...)`. Requires `pip install 'self-heal-llm[claude]' claude-agent-sdk`.

### LangChain / LangGraph (first-class)

```python
from self_heal.integrations.langgraph import healing_tool

@healing_tool(
    "price_from_text",
    description="Extract a price from messy text.",
    verify=lambda r: isinstance(r, float) and r > 0,
)
def price_from_text(text: str) -> float:
    return float(text.replace("$", ""))
```

`healing_tool` mirrors `langchain_core.tools.tool` and stacks `@repair` underneath. The result is a `BaseTool` ready for any LangChain chain or LangGraph agent. Requires `pip install langchain-core langgraph`.

### Other frameworks (decorator stacking)

Examples in [`examples/`](examples):

- [`with_claude_agent_sdk.py`](examples/with_claude_agent_sdk.py)
- [`with_openai_agents.py`](examples/with_openai_agents.py)
- [`with_langchain.py`](examples/with_langchain.py)
- [`with_crewai.py`](examples/with_crewai.py)

## Safety

`self-heal` executes LLM-generated code via `exec()` in the same process by default. Three layers of defense are available:

1. **AST rails** (`SafetyConfig(level="moderate"|"strict")`) block dangerous imports, `eval`/`exec`, introspection escape hatches, and `os.system`-style calls before any code runs.
2. **Subprocess sandbox** (`SafetyConfig(sandbox="subprocess")`) runs each call to the repaired function in a fresh `python -I` child process. Args/return value go over stdin/stdout via pickle. The child inherits none of the caller's globals, so proposals must be self-contained.
3. Same trust boundary as any LLM-in-the-loop system: still do not run against untrusted inputs without network isolation.

```python
from self_heal import repair, SafetyConfig

@repair(safety=SafetyConfig(level="moderate", sandbox="subprocess"))
def parse_price(text: str) -> float:
    ...
```

## Roadmap

- [x] v0.0.1: core repair loop + decorator + Claude backend
- [x] v0.0.2: OpenAI, Gemini, LiteLLM adapters; works with any LLM
- [x] v0.1.0: multi-turn memory, verifiers, test-driven repair, async, benchmark harness
- [x] v0.2.0: repair cache, AST safety rails, event callbacks, pytest plugin, CLI, extended benchmarks
- [x] v0.3.0: subprocess sandbox, `pytest --heal-apply`, QuixBugs benchmark, local-model sweep tooling
- [x] v0.4.0: streaming token events (`propose_chunk`), native async proposers (`apropose`) for all four adapters
- [x] **v0.4.1: sandbox preserves custom exceptions from proposals; `is_git_dirty` fails closed on timeout; Claude Agent SDK and LangChain/LangGraph first-class integrations**
- [ ] v0.5: wasm sandbox, warm subprocess worker pool, first-class CrewAI / OpenAI Agents SDK integrations
- [ ] v1.0: stable API + extended benchmark suite (HumanEval-Fix, Refactory)

## Deeper docs

- [`docs/sandbox-threat-model.md`](docs/sandbox-threat-model.md): what the subprocess sandbox protects against and what it does not. Read before running against untrusted inputs.
- [`docs/custom-proposer.md`](docs/custom-proposer.md): implementing the `LLMProposer` Protocol for an unsupported provider.
- [`docs/faq.md`](docs/faq.md): positioning, cost, safety, integrations, contribution.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide: dev setup, everyday commands, how to add a new LLM proposer or benchmark task, and the PR checklist. Good first issues are tagged [here](https://github.com/Johin2/self-heal/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22).

## Development (quick start)

```bash
git clone https://github.com/Johin2/self-heal.git
cd self-heal
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
# .venv/bin/pip install -e ".[dev]"     # macOS/Linux
pytest
ruff check .
```

Run the benchmark locally:
```bash
python benchmarks/run.py --proposer claude                       # uses ANTHROPIC_API_KEY
python benchmarks/run.py --proposer openai                       # uses OPENAI_API_KEY
python benchmarks/run.py --proposer gemini                       # uses GEMINI_API_KEY
python benchmarks/run.py --suite quixbugs --proposer gemini      # QuixBugs (40 programs, clones on first use)
```

## License

MIT
