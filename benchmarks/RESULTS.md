# Benchmark results

This file collects self-heal benchmark numbers across proposers and models.
Submit a PR appending your own row.

## Default suite (hand-written, 19 tasks)

| Proposer | Model | Attempts | Naive pass | self-heal pass | Delta | Hardware | Submitter |
|----------|-------|----------|------------|----------------|-------|----------|-----------|
| gemini   | gemini-2.5-flash | 3 | 68% (13/19) | 100% (19/19) | +6 | API | @Johin2 |

## QuixBugs suite (40 programs, `--suite quixbugs`)

| Proposer | Model | Attempts | Naive pass | self-heal pass | Delta | Hardware | Submitter |
|----------|-------|----------|------------|----------------|-------|----------|-----------|
| _TBD_    |       |          |            |                |       |          |           |

## How to contribute a row

1. Run the harness against your model of choice:

   ```bash
   # Hosted (API key in env)
   python benchmarks/run.py --proposer gemini --model gemini-2.5-flash

   # Local via Ollama (OpenAI-compatible endpoint — set OPENAI_BASE_URL env var)
   OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama \
       python benchmarks/run.py --proposer openai --model qwen2.5-coder:14b

   # QuixBugs suite
   OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama \
       python benchmarks/run.py --suite quixbugs --proposer openai --model llama3.3:70b
   ```

2. Or sweep several local models at once with the helper script:

   ```bash
   python benchmarks/run_local_sweep.py \
       --models "qwen2.5-coder:14b,llama3.3:70b,deepseek-coder-v2:16b" \
       --base-url http://localhost:11434/v1
   ```

3. Append your row to the table above and open a PR. Include the
   `--attempts` value and (for local models) GPU specs in the "Hardware"
   column (e.g. "RTX 4090 24GB").
