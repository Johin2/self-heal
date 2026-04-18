# FAQ

Questions the project gets asked repeatedly. Skim for the one you are here for.

## Positioning

### Isn't this just "retry with an LLM"?

The category, yes. The difference is three specifics:

1. **Structured memory.** Each retry sees the full history of prior failed proposals, not just the latest failure. The LLM does not repeat the same mistake across attempts.
2. **Test-driven verification, not just "did it not crash."** You pass a list of callable `tests=[...]` or a `verify=...` predicate; the proposal is rejected until all of them pass.
3. **Sandbox and AST rails.** Proposals can be rejected before execution (AST layer) or run in an isolated `python -I` subprocess (sandbox layer) so running LLM code does not automatically mean running arbitrary code in your main process.

See `src/self_heal/propose.py::build_messages` for the exact prompt shape.

### How does this differ from Instructor or Guardrails AI?

Different layer of the stack. Instructor validates the shape of LLM output (Pydantic-typed responses). Guardrails validates content against declarative rules. Both are checkers. self-heal is an actor: when a function fails, it asks the LLM to rewrite the function and retries. They compose — I would actually recommend Instructor + self-heal for structured-output agent tools.

### Why not use LangGraph's built-in retry / LangChain's retry wrapper?

LangGraph retries the whole node with the same code. self-heal rewrites the failing callable itself. Different primitive. If your LangGraph node is a tool whose body you want to self-heal, use the LangChain / LangGraph integration: `from self_heal.integrations.langgraph import healing_tool`. The two retries are complementary.

### Won't frontier models eventually make this unnecessary?

Partly yes. The benchmark already shows the delta compressing: Gemini 2.5 Flash went from 68% naive (in the README's original run) to 84% (current run), and self-heal's ceiling is 95%. As the naive floor rises the absolute delta shrinks.

The value that doesn't compress:
- Production edge cases are the last 5% of cases by definition; that is exactly where agents fail in prod.
- The audit trail and policy layer (the future hosted version) is model-independent.
- Tests are your source of truth regardless of model capability.

If frontier models get so good that no agent ever fails in production, self-heal becomes unnecessary. That is not 2026.

### Why not just use try/except and retry?

try/except with the same code gets you zero additional correctness under a deterministic bug. self-heal proposes a different implementation each time, informed by what failed. For transient failures retry is fine; for logic bugs you need a new implementation.

## Installation and compatibility

### Which Python versions does this support?

3.10 through 3.13. CI runs all four.

### What dependencies do I need?

Zero beyond `pydantic`. The LLM adapters are all optional extras:

```
pip install 'self-heal-llm[claude]'    # Anthropic Claude
pip install 'self-heal-llm[openai]'    # OpenAI + OpenAI-compatible endpoints
pip install 'self-heal-llm[gemini]'    # Google Gemini
pip install 'self-heal-llm[litellm]'   # 100+ providers via LiteLLM
pip install 'self-heal-llm[all]'       # everything
```

### Why is the PyPI name `self-heal-llm` but the import is `self_heal`?

PyPI's similarity filter blocked `self-heal` because of an unrelated existing package. The import name stayed clean. Convention is `from self_heal import repair`.

## Usage

### Sync or async?

Both. The `@repair` decorator auto-detects. Sync functions go through `RepairLoop.run`; `async def` functions go through `RepairLoop.arun` which uses each proposer's native `apropose` when available.

### Can I use this with streaming?

Yes. Register an `on_event` callback and you will get `propose_chunk` events as tokens arrive. All four built-in adapters stream natively. Custom proposers can implement `propose_stream` / `apropose_stream` to participate; see `docs/custom-proposer.md`.

### How do I stop self-heal from actually running the LLM on every call?

Turn on the cache:

```python
@repair(cache_path=".self_heal_cache.db")
def my_fn(...): ...
```

The cache keys on a hash of the source + the failure signature. Identical failures after the first hit serve the previously-accepted repair from SQLite without calling the LLM. Keys are normalized for trivial whitespace and memory addresses so cosmetic edits still hit the cache.

### How much does the repair loop cost in LLM calls?

On the current benchmarks (Gemini 2.5 Flash, 3 max attempts): ~20% more LLM calls than naive single-shot for +2 tasks repaired on both suites. Specifically: default suite 21 calls vs 17 (+23%), QuixBugs 35 vs 30 (+17%). The cache makes repeat failures free.

### Does the LLM see my source code?

Yes. The repair prompt includes the source of the failing function plus the failure payload (traceback or test output). If you are repairing code that contains secrets, redact them before the repair loop runs, or use `prompt_extra=...` to instruct the LLM to avoid emitting secrets.

### Can I use this against real test files, not just inline tests?

Yes, via the pytest plugin. Run `pytest --heal` with a test marked `@pytest.mark.heal(target="mymod.my_fn")` and self-heal will repair `my_fn` using that test as verification. Add `--heal-apply` to write the accepted fix to the source file (with a git-dirty guard and a `.heal-backup` file).

## Safety

### Is the subprocess sandbox safe against adversarial proposals?

It prevents the specific class of attacks documented in `docs/sandbox-threat-model.md`. It does not prevent network exfiltration or filesystem reads, and it does not replace a proper container or VM for adversarial threat models. Read that doc before deploying against untrusted inputs.

### What does the AST safety layer actually block?

`moderate` (default on): calls to `eval`, `exec`, `__import__`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, `os.kill`, `os.remove`, `os.unlink`, `os.rmdir`; imports of `subprocess`, `socket`, `shutil`, `pickle`, `ctypes`, `multiprocessing`, `threading`; attribute access on `__globals__`, `__builtins__`, `__code__`, `__class__`, `__mro__`, `__subclasses__`, `__bases__`, `__dict__`; `global` statements. See `src/self_heal/safety.py` for the exact lists.

`strict`: everything above, plus any import outside a short whitelist of harmless stdlib modules.

## Integrations

### How do I use this with Claude Agent SDK?

```python
from self_heal.integrations.claude_agent_sdk import healing_tool

@healing_tool("my_tool", "description", {"arg": str}, verify=...)
async def my_tool(args):
    ...
```

Returns an `SdkMcpTool` ready for `create_sdk_mcp_server(...)`. The agent sees a standard SDK tool; self-heal repairs the body underneath.

### How do I use this with LangGraph?

```python
from self_heal.integrations.langgraph import healing_tool

@healing_tool("my_tool", description="...", verify=...)
def my_tool(arg: str) -> float:
    ...
```

Returns a LangChain `BaseTool` you can bind to any LangGraph agent.

### CrewAI, OpenAI Agents SDK, others?

Decorator-stacking works for any framework whose tool registration expects a callable:

```python
# from crewai.tools import tool  # or whichever framework
@tool("my_tool")
@repair(tests=[...])
def my_tool(...):
    ...
```

See `examples/` for the patterns. First-class integrations for CrewAI and the OpenAI Agents SDK are roadmap items.

## Contributing

### What is the fastest path to land a PR?

Read `CONTRIBUTING.md`. In short: pick an issue labelled `good first issue`, open a PR, keep changes surgical, run `ruff check .` and `pytest` locally, add tests for new behavior.

### I found a bug. Where do I file it?

Public GitHub issues for regular bugs. If it's a sandbox or AST-rails escape, file a private security advisory: `Johin2/self-heal` → Security → Advisories → Report a vulnerability.

### I want a provider / framework / feature that does not exist. What do I do?

Two options:
1. Open an issue describing the use case, tagging `enhancement`. We talk about it first.
2. Implement it in a fork and open a PR. For adapters, `docs/custom-proposer.md` walks through the shape.
