# Writing a custom LLM proposer

self-heal ships four adapters (Claude, OpenAI, Gemini, LiteLLM) that cover the providers most people need. If you are calling an unsupported provider, fine-tuning a local model, or wiring self-heal into a mock for tests, implement the `LLMProposer` Protocol. This doc walks through the minimum, the optional extensions, and testing.

## The Protocol

```python
class LLMProposer(Protocol):
    def propose(self, system: str, user: str) -> str: ...
```

That is the entire required surface: one sync method that takes a system prompt and a user prompt and returns the raw text response from the LLM. self-heal handles the rest — prompt construction, code extraction, verification, retry.

## Minimum working example

```python
import httpx
from self_heal import RepairLoop

class MyProposer:
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key

    def propose(self, system: str, user: str) -> str:
        response = httpx.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 2048,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

loop = RepairLoop(proposer=MyProposer("https://my-llm/v1/chat", "..."))
result = loop.run(my_fn, args=(...))
```

That is it. Your proposer now works everywhere self-heal accepts a proposer: the `@repair` decorator, the `RepairLoop`, the pytest plugin, the CLI.

## Optional: async

If your provider has a native async client, implement `apropose`. `RepairLoop.arun` will prefer it and skip the `asyncio.to_thread` fallback.

```python
class MyProposer:
    def propose(self, system: str, user: str) -> str:
        ...

    async def apropose(self, system: str, user: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(...)
            return response.json()["choices"][0]["message"]["content"]
```

## Optional: streaming

Implement `propose_stream` (sync) or `apropose_stream` (async) to emit `propose_chunk` events as tokens arrive. self-heal accumulates the stream and uses the final string as the proposal.

```python
from collections.abc import Iterator

class MyProposer:
    def propose(self, system: str, user: str) -> str:
        ...

    def propose_stream(self, system: str, user: str) -> Iterator[str]:
        with httpx.stream("POST", ..., json={"stream": True, ...}) as r:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    delta = parse_sse_delta(line)
                    if delta:
                        yield delta
```

If streaming raises mid-way, self-heal silently falls back to `propose()`. Issue #13 tracks adding observability around this fallback.

## Testing your proposer

Use a scripted proposer in unit tests to avoid API calls. This is exactly how self-heal tests its own repair loop.

```python
class ScriptedProposer:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def propose(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._responses.pop(0)

def test_my_integration():
    good_source = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([good_source])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))
    assert result.succeeded
    assert result.final_value == 0
    assert len(proposer.calls) == 1
```

## Prompt contract

self-heal assumes `propose()` returns text that contains a complete Python function definition. Providers can return either bare code or code inside Markdown fences — self-heal's `extract_code()` handles both. If your provider wraps responses in some other envelope, extract the raw text before returning.

The two prompts you will receive:

- **`system`**: Role-setting and failure taxonomy. Includes the original buggy source, the failure classification, and instructions like "return only the corrected function."
- **`user`**: The specific failure payload (traceback, verifier output, failing test output) plus a structured history of prior failed attempts if this is a retry.

You should not need to modify these prompts from your proposer. If you need to inject provider-specific instructions, use the `prompt_extra` parameter on `@repair` or `RepairLoop`.

## When to ship a new built-in adapter vs a custom proposer

Custom proposer is the right answer when:
- Your provider has a bespoke API that does not match OpenAI chat-completions shape
- You want provider-specific quirks (custom timeout, retry, header auth) that a generic wrapper would obscure
- You are testing self-heal and need a fake

Ship a new adapter in `src/self_heal/llm/` and send a PR when:
- The provider has an OpenAI-compatible endpoint that `OpenAIProposer(base_url=...)` does not already cover
- The provider is popular enough that a first-class import (`from self_heal.llm import YourProposer`) would save other users from writing the same custom class
- You are willing to maintain it alongside the four existing adapters

See `src/self_heal/llm/_claude.py` for the cleanest adapter template: ~80 lines, lazy-imports the SDK, handles sync + async + streaming, reads the API key from env with an `api_key=` override.
