# self-heal

[![CI](https://github.com/Johin2/self-heal/actions/workflows/ci.yml/badge.svg)](https://github.com/Johin2/self-heal/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/self-heal-llm.svg)](https://pypi.org/project/self-heal-llm/)
[![Python](https://img.shields.io/pypi/pyversions/self-heal-llm.svg)](https://pypi.org/project/self-heal-llm/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Automatic repair for failing Python code, powered by any LLM.

When a function fails, `self-heal` catches the exception, analyzes it with an LLM, proposes a repaired version, and retries. One decorator. Works with Claude, OpenAI, Gemini, and 100+ other providers.

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

## Using different providers

**Claude (default):**
```python
from self_heal import repair

@repair()  # uses ClaudeProposer under the hood
def my_fn(...): ...
```

**OpenAI:**
```python
from self_heal import repair
from self_heal.llm import OpenAIProposer

@repair(proposer=OpenAIProposer(model="gpt-5"))
def my_fn(...): ...
```

**Gemini:**
```python
from self_heal import repair
from self_heal.llm import GeminiProposer

@repair(proposer=GeminiProposer(model="gemini-2.5-pro"))
def my_fn(...): ...
```

**Any OpenAI-compatible endpoint (OpenRouter, Groq, Ollama, ...):**
```python
from self_heal.llm import OpenAIProposer

# OpenRouter — hundreds of models through one key
proposer = OpenAIProposer(
    model="google/gemini-2.5-pro",
    base_url="https://openrouter.ai/api/v1",
)

# Groq — fast inference
proposer = OpenAIProposer(
    model="llama-3.3-70b-versatile",
    base_url="https://api.groq.com/openai/v1",
)

# Local Ollama
proposer = OpenAIProposer(
    model="llama3.3",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)
```

**LiteLLM catch-all (100+ providers):**
```python
from self_heal.llm import LiteLLMProposer

proposer = LiteLLMProposer(model="anthropic/claude-sonnet-4-6")
proposer = LiteLLMProposer(model="bedrock/anthropic.claude-3-5-sonnet")
proposer = LiteLLMProposer(model="vertex_ai/gemini-2.5-pro")
proposer = LiteLLMProposer(model="cohere/command-r-plus")
```

## Why this exists

AI coding agents fail on a lot of real tasks. The industry's current answer is "retry and hope." That's not a strategy.

`self-heal` treats repair as a first-class primitive: diagnose the failure, propose a targeted fix, verify, retry. A thin library you can wrap around any Python function or agent tool.

## How it works

1. **Catch** the exception and capture inputs, traceback, and failure type.
2. **Classify** the failure (validation, exception, assertion).
3. **Propose** a repaired function via LLM with a failure-aware prompt.
4. **Recompile** the proposed function into the running process.
5. **Retry** with the same inputs.

All within a single decorator boundary.

## API

**Decorator:**
```python
from self_heal import repair

@repair(max_attempts=3, model="claude-sonnet-4-6", verbose=True)
def my_tool(x): ...

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

**Custom proposer:**
```python
from self_heal.llm import LLMProposer

class MyProposer:
    def propose(self, system: str, user: str) -> str:
        # ... your logic ...
        return "def my_tool(x): return x * 2"
```

## Safety

`self-heal` executes LLM-generated code via `exec()` in the same process. Same trust boundary as any LLM-in-the-loop system: do not run against untrusted inputs without a sandbox. Sandboxed execution is on the roadmap.

## Roadmap

- [x] v0.0.1: core repair loop + decorator + Claude backend
- [x] v0.0.2: OpenAI, Gemini, LiteLLM adapters — works with any LLM
- [ ] v0.1: user-provided verifiers (beyond exception-catching)
- [ ] v0.2: telemetry + before/after success metrics
- [ ] v0.3: async support
- [ ] v0.4: sandboxed execution
- [ ] v0.5: repair persistence (learn from past fixes)
- [ ] v1.0: stable API + benchmark suite

## Development

```bash
git clone https://github.com/Johin2/self-heal.git
cd self-heal
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows
# .venv/bin/pip install -e ".[dev]"     # macOS/Linux
pytest
```

## License

MIT
