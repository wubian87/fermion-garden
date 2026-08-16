"""Stable data contracts for ctx-key v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

Action = Literal["record", "select", "keep", "evict", "recall", "retain", "conflict"]


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One candidate context item.

    ``created_at`` is a caller-provided monotonic order, not wall-clock time.
    Pinned items are never evicted by ``compact``.
    """

    id: str
    text: str
    source: str = "unknown"
    tags: tuple[str, ...] = ()
    created_at: int = 0
    pinned: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ContextItem.id must not be blank")
        if not self.text.strip():
            raise ValueError("ContextItem.text must not be blank")


@dataclass(frozen=True, slots=True)
class Decision:
    item_id: str
    action: Action
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class ContextBundle:
    operation: Literal["select", "compact", "recall"]
    criterion: str
    target_role: str
    selected_ids: tuple[str, ...]
    evicted_ids: tuple[str, ...]
    recalled_ids: tuple[str, ...]
    decisions: tuple[Decision, ...]
    context_version: int
    trace_id: str
    budget: int
    conflict: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "criterion": self.criterion,
            "target_role": self.target_role,
            "selected_ids": list(self.selected_ids),
            "evicted_ids": list(self.evicted_ids),
            "recalled_ids": list(self.recalled_ids),
            "decisions": [
                {
                    "item_id": decision.item_id,
                    "action": decision.action,
                    "score": decision.score,
                    "reason": decision.reason,
                }
                for decision in self.decisions
            ],
            "context_version": self.context_version,
            "trace_id": self.trace_id,
            "budget": self.budget,
            "conflict": self.conflict,
        }

