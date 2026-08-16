---
name: ctx-key
description: Assemble minimal, auditable and reversible context bundles for multi-agent handoffs. Use when an agent must choose what the next role should read, compact an over-budget shared context without permanent deletion, or recall previously evicted evidence after a task change or verification failure.
---

# ctx-key

Use the installed `fermion_garden` package to select, compact and recall shared context. Treat the result as a recommendation with an audit trail, not as permission to delete source material.

## Workflow

1. State the current task and the receiving role explicitly.
2. Turn candidate material into `ContextItem` records with stable ids and sources.
3. Pin non-negotiable constraints and pass any additional required ids.
4. Call `select` before a handoff. Give the receiver only the selected bundle plus references to the source store.
5. Call `compact` only under a real position or budget constraint. Preserve every evicted item in the recoverable store.
6. Call `recall` when the task criterion changes, verification fails, or a user explicitly asks to revisit old evidence.
7. Keep the returned reasons, `context_version` and `trace_id` with the handoff record.

## Safety and failure rules

- Do not permanently delete candidate content.
- If pinned and required items exceed the budget, report the conflict and leave state unchanged.
- If the criterion is blank or the scorer has no useful distinction, keep the context and report the limitation.
- Do not treat shorter context as success. Validate the downstream task result independently.
- Do not let a fixer use this Skill to alter acceptance tests or self-approve a patch.
- Treat the v0.1 lexical scorer as an offline baseline. Revalidate any replacement embedding or model provider.

## Minimal use

```python
from fermion_garden import ContextItem, CtxKey

garden = CtxKey([ContextItem(id="issue", text="timezone boundary fails", pinned=True)])
bundle = garden.select(task_state="find the cause", target_role="investigator", budget=1)
```

Read the repository `STATUS.md` and `docs/limitations.md` before making product or efficacy claims.
