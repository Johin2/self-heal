# self-heal

> Automatic repair for failing Python code, powered by LLMs.

When a function fails, `self-heal` catches the exception, analyzes it with an LLM, proposes a repaired version, and retries. One decorator.

```python
from self_heal import repair

@repair(max_attempts=3)
def extract_price(text: str) -> float:
    # Naive: only handles "$X.YY"
    return float(text.replace("$", ""))

print(extract_price("$12.99"))    # 12.99
print(extract_price("₹1,299"))    # 1299.0  (repaired)
print(extract_price("€5,49"))     # 5.49    (repaired)
```

## Install

```bash
pip install self-heal
# or
uv add self-heal
```

Set `ANTHROPIC_API_KEY` in your environment.

## Why this exists

AI coding agents fail on a lot of real tasks. The current industry answer is "retry and hope." That's not a strategy.

`self-heal` treats repair as a first-class primitive: diagnose the failure, propose a targeted fix, verify, retry. It's a thin library you can wrap around any Python function or agent tool.

Built on ongoing code-repair research (RepairBench, NeurIPS 2026).

## How it works

1. **Catch** the exception and capture inputs, traceback, and failure type.
2. **Classify** the failure (validation, exception, assertion).
3. **Propose** a repaired function via LLM with a failure-aware prompt.
4. **Recompile** the proposed function into the running process.
5. **Retry** with the same inputs.

All within a single decorator boundary.

## API

**Decorator (simple case):**

```python
from self_heal import repair

@repair(max_attempts=3, model="claude-sonnet-4-6", verbose=True)
def my_tool(x):
    ...

my_tool(42)
my_tool.last_repair  # -> RepairResult with full attempt history
```

**Loop (for advanced use):**

```python
from self_heal import RepairLoop

loop = RepairLoop(max_attempts=5, verbose=True)
result = loop.run(my_tool, args=(42,))
if result.succeeded:
    print(result.final_value)
else:
    print(result.attempts[-1].failure.traceback)
```

**Custom LLM / testing:**

```python
from self_heal import RepairLoop

class MyProposer:
    def propose(self, system: str, user: str) -> str:
        return "def my_tool(x): return x * 2"

loop = RepairLoop(proposer=MyProposer())
```

## Safety

`self-heal` executes LLM-generated code via `exec()` in the same process. This is the same trust boundary as any LLM-in-the-loop system: do not run against untrusted inputs without a sandbox. Sandboxed execution is on the roadmap.

## Roadmap

- [x] v0.0.1: core repair loop + decorator + Claude backend
- [ ] v0.1: user-provided verifiers (beyond exception-catching)
- [ ] v0.2: telemetry + before/after success metrics
- [ ] v0.3: alternate LLM backends (OpenAI, local models)
- [ ] v0.4: sandboxed execution
- [ ] v0.5: repair persistence (learn from past fixes)
- [ ] v1.0: NeurIPS 2026 paper co-release

## Development

```bash
git clone https://github.com/Johin2/self-heal.git
cd self-heal
uv pip install -e ".[dev]"
pytest
```

## License

MIT
