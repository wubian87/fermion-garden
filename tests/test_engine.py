from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey
from fermion_garden.lexical import tokenize


def sample_items() -> list[ContextItem]:
    return [
        ContextItem("issue", "timezone boundary fails at midnight", pinned=True, created_at=1),
        ContextItem("trace", "timezone normalize_offset stacktrace", created_at=2),
        ContextItem("contract", "preserve ISO offset formatting", created_at=3),
        ContextItem("old", "retired timezone sign reversal hypothesis", created_at=4),
        ContextItem("noise", "CSV delimiter differs on Windows", created_at=5),
    ]


class CtxKeyTests(unittest.TestCase):
    def test_select_is_deterministic_and_keeps_pinned_item(self) -> None:
        garden = CtxKey(sample_items())
        first = garden.select(task_state="timezone midnight", target_role="fixer", budget=2)
        second = garden.select(task_state="timezone midnight", target_role="fixer", budget=2)
        self.assertEqual(first.selected_ids, second.selected_ids)
        self.assertIn("issue", first.selected_ids)
        self.assertEqual(len(first.selected_ids), 2)

    def test_compact_is_reversible(self) -> None:
        garden = CtxKey(sample_items())
        compacted = garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        self.assertTrue(compacted.evicted_ids)
        self.assertEqual(set(compacted.evicted_ids), set(garden.recoverable_ids))
        recalled = garden.recall("retired timezone sign reversal", budget=1)
        self.assertEqual(recalled.recalled_ids, ("old",))
        self.assertIn("old", garden.active_ids)
        self.assertNotIn("old", garden.recoverable_ids)

    def test_compact_never_evicts_pinned_item(self) -> None:
        garden = CtxKey(sample_items())
        garden.compact(task_state="CSV delimiter", target_role="fixer", budget=1)
        self.assertIn("issue", garden.active_ids)

    def test_mandatory_budget_conflict_does_not_change_state(self) -> None:
        garden = CtxKey(sample_items())
        before = garden.snapshot()
        bundle = garden.compact(
            task_state="timezone",
            target_role="fixer",
            budget=1,
            required_ids=("trace",),
        )
        self.assertIsNotNone(bundle.conflict)
        self.assertEqual(before["active_ids"], garden.snapshot()["active_ids"])
        self.assertEqual(before["context_version"], garden.context_version)

    def test_no_score_distinction_fails_closed(self) -> None:
        garden = CtxKey([
            ContextItem("a", "alpha"),
            ContextItem("b", "beta"),
        ])
        before = garden.snapshot()
        bundle = garden.compact(task_state="unrelated", target_role="fixer", budget=1)
        self.assertIsNotNone(bundle.conflict)
        self.assertIn("no positive signal", bundle.conflict)
        self.assertEqual(before["active_ids"], garden.snapshot()["active_ids"])
        self.assertEqual(before["context_version"], garden.context_version)

    def test_float_budget_rejected(self) -> None:
        garden = CtxKey(sample_items())
        with self.assertRaises(ValueError):
            garden.select(task_state="timezone", target_role="fixer", budget=2.5)
        with self.assertRaises(ValueError):
            garden.compact(task_state="timezone", target_role="fixer", budget=True)

    def test_cutoff_tie_fails_closed(self) -> None:
        garden = CtxKey([
            ContextItem("older", "same relevant phrase", created_at=1),
            ContextItem("newer", "same relevant phrase", created_at=2),
            ContextItem("noise", "different", created_at=3),
        ])
        bundle = garden.compact(task_state="relevant phrase", target_role="fixer", budget=1)
        self.assertIsNotNone(bundle.conflict)
        self.assertEqual(bundle.selected_ids, ())
        self.assertEqual(garden.recoverable_ids, ())

    def test_record_rejects_active_and_recoverable_id_collisions_atomically(self) -> None:
        garden = CtxKey(sample_items())
        before = garden.snapshot()
        with self.assertRaises(ValueError):
            garden.record([ContextItem("issue", "replacement")])
        self.assertEqual(before, garden.snapshot())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        self.assertIn("old", garden.recoverable_ids)
        before_recoverable_collision = garden.snapshot()
        with self.assertRaises(ValueError):
            garden.record([ContextItem("old", "replacement")])
        self.assertEqual(before_recoverable_collision, garden.snapshot())

    def test_record_rejects_blank_reason(self) -> None:
        garden = CtxKey()
        with self.assertRaises(ValueError):
            garden.record([ContextItem("item", "text")], reason="  ")
        self.assertEqual(garden.context_version, 0)
        with self.assertRaises(ValueError):
            garden.record([], reason="   ")
        self.assertEqual(garden.context_version, 0)

    def test_recall_marks_retained_items(self) -> None:
        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        recalled = garden.recall("retired timezone sign reversal", budget=1)
        self.assertEqual(recalled.recalled_ids, ("old",))
        retained_actions = [
            event.action
            for event in garden.ledger.events
            if event.operation == "recall" and event.item_id in ("contract", "noise")
        ]
        self.assertTrue(retained_actions)
        self.assertTrue(all(action == "retain" for action in retained_actions))

    def test_empty_context_and_empty_recall_are_audited(self) -> None:
        garden = CtxKey()
        selected = garden.select(task_state="task", target_role="fixer", budget=1)
        self.assertIsNotNone(selected.conflict)
        recalled = garden.recall("new evidence", budget=1)
        self.assertEqual(recalled.recalled_ids, ())
        operations = [event.operation for event in garden.ledger.events]
        self.assertIn("select", operations)
        self.assertIn("recall", operations)

    def test_audit_records_reason_version_and_trace(self) -> None:
        garden = CtxKey(sample_items())
        garden.select(
            task_state="timezone",
            target_role="investigator",
            budget=2,
            trace_id="test-trace",
        )
        events = [event for event in garden.ledger.events if event.trace_id == "test-trace"]
        self.assertTrue(events)
        self.assertTrue(all(event.reason for event in events))
        self.assertTrue(all(event.context_version == garden.context_version for event in events))
        self.assertTrue(all(event.criterion for event in events))
        self.assertTrue(all(event.target_role == "investigator" for event in events))
        self.assertTrue(all(event.budget == 2 for event in events))
        self.assertTrue(all(event.candidate_ids for event in events))
        self.assertTrue(all(event.item_content_sha256 for event in events if event.item_id != "*"))
        self.assertIn('"trace_id": "test-trace"', garden.ledger.to_jsonl())

    def test_invalid_requests_fail_closed(self) -> None:
        garden = CtxKey(sample_items())
        with self.assertRaises(ValueError):
            garden.select(task_state="", target_role="fixer", budget=1)
        with self.assertRaises(ValueError):
            garden.select(task_state="task", target_role="fixer", budget=0)
        with self.assertRaises(KeyError):
            garden.select(task_state="task", target_role="fixer", budget=2, required_ids=("missing",))

    def test_chinese_bigrams_do_not_cross_gaps(self) -> None:
        self.assertIn("北京", tokenize("北京"))
        self.assertNotIn("北京", tokenize("北 A 京"))


if __name__ == "__main__":
    unittest.main()
