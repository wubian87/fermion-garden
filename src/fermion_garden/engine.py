"""Reversible context selection engine.

The scorer is deliberately simple and offline. It is a baseline implementation,
not a claim that lexical relevance solves multi-agent context management.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
import uuid

from .ledger import DecisionLedger
from .lexical import score_items
from .models import ContextBundle, ContextItem, Decision


class CtxKey:
    """Maintain active and recoverable context with an append-only decision ledger."""

    def __init__(self, items: Iterable[ContextItem] = ()) -> None:
        self._active: OrderedDict[str, ContextItem] = OrderedDict()
        self._recoverable: OrderedDict[str, ContextItem] = OrderedDict()
        self._version = 0
        self.ledger = DecisionLedger()
        if items:
            self.record(items, reason="initial context")

    @property
    def context_version(self) -> int:
        return self._version

    @property
    def active_ids(self) -> tuple[str, ...]:
        return tuple(self._active)

    @property
    def recoverable_ids(self) -> tuple[str, ...]:
        return tuple(self._recoverable)

    def record(self, items: Iterable[ContextItem], *, reason: str = "new evidence") -> tuple[str, ...]:
        item_list = list(items)
        if not reason.strip():
            raise ValueError("record reason must not be blank")
        if not item_list:
            return ()
        if len({item.id for item in item_list}) != len(item_list):
            raise ValueError("record received duplicate item ids")
        existing_ids = set(self._active) | set(self._recoverable)
        collisions = sorted(item.id for item in item_list if item.id in existing_ids)
        if collisions:
            raise ValueError(f"record ids already exist; use a versioned id instead: {collisions}")
        self._version += 1
        trace_id = self._trace_id()
        decisions: list[Decision] = []
        for item in item_list:
            self._active[item.id] = item
            self._recoverable.pop(item.id, None)
            decisions.append(Decision(item.id, "record", 0.0, reason))
        self.ledger.append(
            operation="record",
            trace_id=trace_id,
            context_version=self._version,
            decisions=decisions,
            criterion=reason.strip(),
            target_role="system",
            budget=None,
            candidate_items=item_list,
        )
        return tuple(item.id for item in item_list)

    def select(
        self,
        *,
        task_state: str,
        target_role: str,
        budget: int,
        required_ids: Iterable[str] = (),
        trace_id: str | None = None,
    ) -> ContextBundle:
        bundle = self._plan_select(
            task_state=task_state,
            target_role=target_role,
            budget=budget,
            required_ids=required_ids,
            trace_id=trace_id,
        )
        self._write_bundle(bundle)
        return bundle

    def _plan_select(
        self,
        *,
        task_state: str,
        target_role: str,
        budget: int,
        required_ids: Iterable[str] = (),
        trace_id: str | None = None,
    ) -> ContextBundle:
        self._validate_request(task_state, target_role, budget)
        trace = trace_id or self._trace_id()
        required = set(required_ids)
        missing = sorted(required - set(self._active))
        if missing:
            raise KeyError(f"required ids are not active: {missing}")
        if not self._active:
            decisions = (Decision("*", "conflict", 0.0, "no active context to select"),)
            bundle = ContextBundle(
                operation="select",
                criterion=f"target_role={target_role}; task={task_state.strip()}",
                target_role=target_role,
                selected_ids=(),
                evicted_ids=(),
                recalled_ids=(),
                decisions=decisions,
                context_version=self._version,
                trace_id=trace,
                budget=budget,
                conflict="no active context to select; no state changed",
            )
            return bundle
        pinned = {item.id for item in self._active.values() if item.pinned}
        mandatory = required | pinned
        criterion = f"target_role={target_role}; task={task_state.strip()}"
        if len(mandatory) > budget:
            decisions = tuple(
                Decision(item_id, "conflict", 0.0, "mandatory items exceed budget")
                for item_id in sorted(mandatory)
            )
            bundle = ContextBundle(
                operation="select",
                criterion=criterion,
                target_role=target_role,
                selected_ids=(),
                evicted_ids=(),
                recalled_ids=(),
                decisions=decisions,
                context_version=self._version,
                trace_id=trace,
                budget=budget,
                conflict="mandatory items exceed budget; no state changed",
            )
            return bundle

        scores = score_items(criterion, self._active.values())
        eligible_scores = sorted(
            (scores[item.id] for item in self._active.values() if item.id not in mandatory),
            reverse=True,
        )
        open_slots = budget - len(mandatory)
        needs_choice = len(eligible_scores) > open_slots
        no_positive_signal = needs_choice and open_slots > 0 and eligible_scores[0] <= 0
        cutoff_tie = (
            needs_choice
            and open_slots > 0
            and not no_positive_signal
            and abs(eligible_scores[open_slots - 1] - eligible_scores[open_slots]) <= 1e-12
        )
        if no_positive_signal or cutoff_tie:
            conflict_reason = (
                "scorer has no positive signal" if no_positive_signal else "selection cutoff is tied"
            )
            decisions = tuple(
                Decision(item.id, "conflict", scores[item.id], conflict_reason)
                for item in self._active.values()
            )
            bundle = ContextBundle(
                operation="select",
                criterion=criterion,
                target_role=target_role,
                selected_ids=(),
                evicted_ids=(),
                recalled_ids=(),
                decisions=decisions,
                context_version=self._version,
                trace_id=trace,
                budget=budget,
                conflict=f"{conflict_reason}; no state changed",
            )
            return bundle
        ranked = sorted(
            self._active.values(),
            key=lambda item: (-scores[item.id], -item.created_at, item.id),
        )
        selected = list(sorted(mandatory))
        for item in ranked:
            if item.id not in mandatory and len(selected) < budget:
                selected.append(item.id)
        selected_set = set(selected)
        decisions = tuple(
            Decision(
                item.id,
                "select" if item.id in selected_set else "keep",
                scores[item.id],
                "mandatory" if item.id in mandatory else (
                    "within relevance budget" if item.id in selected_set else "outside current selection budget"
                ),
            )
            for item in ranked
        )
        bundle = ContextBundle(
            operation="select",
            criterion=criterion,
            target_role=target_role,
            selected_ids=tuple(selected),
            evicted_ids=(),
            recalled_ids=(),
            decisions=decisions,
            context_version=self._version,
            trace_id=trace,
            budget=budget,
        )
        return bundle

    def compact(
        self,
        *,
        task_state: str,
        target_role: str,
        budget: int,
        required_ids: Iterable[str] = (),
        trace_id: str | None = None,
    ) -> ContextBundle:
        trace = trace_id or self._trace_id()
        preview = self._plan_select(
            task_state=task_state,
            target_role=target_role,
            budget=budget,
            required_ids=required_ids,
            trace_id=trace,
        )
        if preview.conflict:
            bundle = ContextBundle(
                operation="compact",
                criterion=preview.criterion,
                target_role=target_role,
                selected_ids=preview.selected_ids,
                evicted_ids=(),
                recalled_ids=(),
                decisions=preview.decisions,
                context_version=self._version,
                trace_id=trace,
                budget=budget,
                conflict=preview.conflict,
            )
            self._write_bundle(bundle)
            return bundle

        selected = set(preview.selected_ids)
        evicted = tuple(item_id for item_id in self._active if item_id not in selected)
        if evicted:
            self._version += 1
            for item_id in evicted:
                self._recoverable[item_id] = self._active.pop(item_id)
        score_by_id = {decision.item_id: decision.score for decision in preview.decisions}
        decisions = tuple(
            Decision(
                item_id,
                "keep" if item_id in selected else "evict",
                score_by_id[item_id],
                "kept for current task" if item_id in selected else "reversibly moved under budget pressure",
            )
            for item_id in score_by_id
        )
        bundle = ContextBundle(
            operation="compact",
            criterion=preview.criterion,
            target_role=target_role,
            selected_ids=preview.selected_ids,
            evicted_ids=evicted,
            recalled_ids=(),
            decisions=decisions,
            context_version=self._version,
            trace_id=trace,
            budget=budget,
        )
        self._write_bundle(bundle)
        return bundle

    def recall(
        self,
        trigger: str,
        *,
        budget: int,
        target_role: str = "unspecified",
        trace_id: str | None = None,
    ) -> ContextBundle:
        self._validate_request(trigger, target_role, budget)
        trace = trace_id or self._trace_id()
        scores = score_items(trigger, self._recoverable.values())
        ranked = sorted(
            self._recoverable.values(),
            key=lambda item: (-scores[item.id], -item.created_at, item.id),
        )
        recalled = tuple(item.id for item in ranked if scores[item.id] > 0)[:budget]
        if recalled:
            self._version += 1
            for item_id in recalled:
                self._active[item_id] = self._recoverable.pop(item_id)
        decisions = tuple(
            Decision(
                item.id,
                "recall" if item.id in recalled else "retain",
                scores[item.id],
                "matched recall trigger" if item.id in recalled else "not recalled for this trigger",
            )
            for item in ranked
        )
        if not decisions:
            decisions = (Decision("*", "retain", 0.0, "no recoverable context matched trigger"),)
        bundle = ContextBundle(
            operation="recall",
            criterion=trigger.strip(),
            target_role=target_role,
            selected_ids=tuple(self._active),
            evicted_ids=(),
            recalled_ids=recalled,
            decisions=decisions,
            context_version=self._version,
            trace_id=trace,
            budget=budget,
        )
        self._write_bundle(bundle)
        return bundle

    def snapshot(self) -> dict[str, object]:
        return {
            "context_version": self._version,
            "active_ids": list(self._active),
            "recoverable_ids": list(self._recoverable),
            "ledger_events": len(self.ledger.events),
        }

    @staticmethod
    def _trace_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _validate_request(criterion: str, target_role: str, budget: int) -> None:
        if not criterion.strip():
            raise ValueError("criterion/task state must not be blank")
        if not target_role.strip():
            raise ValueError("target_role must not be blank")
        if isinstance(budget, bool) or not isinstance(budget, int):
            raise ValueError("budget must be an integer")
        if budget < 1:
            raise ValueError("budget must be at least 1")

    def _write_bundle(self, bundle: ContextBundle) -> None:
        candidate_items = [*self._active.values(), *self._recoverable.values()]
        self.ledger.append(
            operation=bundle.operation,
            trace_id=bundle.trace_id,
            context_version=bundle.context_version,
            decisions=bundle.decisions,
            criterion=bundle.criterion,
            target_role=bundle.target_role,
            budget=bundle.budget,
            candidate_items=candidate_items,
            conflict=bundle.conflict,
        )
