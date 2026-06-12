"""First-class integrations with popular agent frameworks.

Each submodule is lazy-imported so missing framework SDKs don't break
`import self_heal`.

Available integrations:
- `self_heal.integrations.claude_agent_sdk` — healing_tool for Claude Agent SDK
- `self_heal.integrations.langgraph` — healing_tool for LangChain / LangGraph
- `self_heal.integrations.openai_agents` — healing_tool for OpenAI Agents SDK

See `examples/` for CrewAI and other decorator-stacking patterns.
"""
