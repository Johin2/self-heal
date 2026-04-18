# self-heal docs

Focused markdown for topics too long for the main README.

| Doc | For |
|---|---|
| [`sandbox-threat-model.md`](sandbox-threat-model.md) | Anyone running self-heal against untrusted inputs or deploying to production. What the subprocess sandbox protects against and what it does not. |
| [`custom-proposer.md`](custom-proposer.md) | Anyone wiring self-heal into an LLM provider that isn't in the four built-in adapters. Also: anyone writing a mock proposer for tests. |
| [`faq.md`](faq.md) | Positioning, installation, cost, safety, integration, and contribution questions in one place. |

Everything in this directory is plain markdown. No docs site, no build step. GitHub renders it natively.
