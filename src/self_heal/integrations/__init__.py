"""First-class integrations with popular agent frameworks.

Each submodule is lazy-imported so missing framework SDKs don't break
`import self_heal`.

Available integrations:
- `self_heal.integrations.claude_agent_sdk` — healing_tool decorator
  combining `@tool` (Claude Agent SDK) with `@repair` (self-heal).

More integrations (CrewAI, LangGraph) are roadmap items; see the
`examples/` directory for the decorator-stacking pattern today.
"""
