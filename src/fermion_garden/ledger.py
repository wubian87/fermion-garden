"""Append-only in-memory audit ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    sequence: int
    timestamp: str
    operation: str
    trace_id: str
    context_version: int
    item_id: str
    action: str
    score: float
    reason: str
    criterion: str
    target_role: str
    budget: int | None
    candidate_ids: tuple[str, ...]
    item_source: str | None
    item_content_sha256: str | None
    conflict: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "trace_id": self.trace_id,
            "context_version": self.context_version,
            "item_id": self.item_id,
            "action": self.action,
            "score": self.score,
            "reason": self.reason,
            "criterion": self.criterion,
            "target_role": self.target_role,
            "budget": self.budget,
            "candidate_ids": list(self.candidate_ids),
            "item_source": self.item_source,
            "item_content_sha256": self.item_content_sha256,
            "conflict": self.conflict,
        }


class DecisionLedger:
    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []

    @property
    def events(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._events)

    def append(
        self,
        *,
        operation: str,
        trace_id: str,
        context_version: int,
        decisions: Iterable[Any],
        criterion: str,
        target_role: str,
        budget: int | None,
        candidate_items: Iterable[Any],
        conflict: str | None = None,
    ) -> None:
        item_index = {item.id: item for item in candidate_items}
        candidate_ids = tuple(sorted(item_index))
        for decision in decisions:
            item = item_index.get(decision.item_id)
            self._events.append(
                LedgerEvent(
                    sequence=len(self._events) + 1,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    operation=operation,
                    trace_id=trace_id,
                    context_version=context_version,
                    item_id=decision.item_id,
                    action=decision.action,
                    score=decision.score,
                    reason=decision.reason,
                    criterion=criterion,
                    target_role=target_role,
                    budget=budget,
                    candidate_ids=candidate_ids,
                    item_source=item.source if item is not None else None,
                    item_content_sha256=(
                        hashlib.sha256(
                            (item.text + "\x1f" + "\x1f".join(item.tags)).encode("utf-8")
                        ).hexdigest()
                        if item is not None
                        else None
                    ),
                    conflict=conflict,
                )
            )

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for event in self._events
        )
