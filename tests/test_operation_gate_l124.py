from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey
from fermion_garden.ledger import LEDGER_OPERATIONS, LedgerEvent
from fermion_garden.models import Decision


def sample_items() -> list[ContextItem]:
    return [
        ContextItem("issue", "timezone boundary fails at midnight", pinned=True, created_at=1),
        ContextItem("trace", "timezone normalize_offset stacktrace", created_at=2),
        ContextItem("contract", "preserve ISO offset formatting", created_at=3),
    ]


class OperationGateTests(unittest.TestCase):
    def test_record_operation_passes_gate_l124(self) -> None:
        # L12.2 §C.2 园主点名的锁：值域基准是账面四旧值（record 经 CtxKey.record 直接
        # ledger.append 落账、不经 ContextBundle），⛔ 不是 models.py:44 Literal 的三值。
        # 漏 record ⟹ 任何含 record 行的账在读写两侧逐行 ValueError（本测试必红）。
        garden = CtxKey(sample_items())
        self.assertEqual(
            [e.operation for e in garden.ledger.events if e.operation == "record"],
            ["record", "record", "record"],
        )
        self.assertIn("record", LEDGER_OPERATIONS)
        # 恢复路径：record 行经 save→load_from 全链不炸（漏 record 时此处逐行炸）。
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
            self.assertEqual(
                [e.operation for e in restored.ledger.events if e.operation == "record"],
                ["record", "record", "record"],
            )

    def test_known_operations_pass_gate_l124(self) -> None:
        # 四旧值＋新值 scan：直接构造 LedgerEvent 全放行（值域含全部旧值∪新值）。
        for operation in ("record", "select", "compact", "recall", "scan"):
            event = LedgerEvent(
                sequence=1, timestamp="2026-08-21T00:00:00+00:00", operation=operation,
                trace_id="t", context_version=1, item_id="a", action="keep",
                score=1.0, reason="r", criterion="c", target_role="t", budget=1,
                candidate_ids=("a",), item_source=None, item_content_sha256=None,
                conflict=None,
            )
            self.assertEqual(event.operation, operation)

    def test_unknown_operation_refused_on_both_sides_l124(self) -> None:
        # 写侧两路（直接构造、经 ledger.append）＋读侧一路（手写 JSON 经 load_from）
        # 都 ValueError，⛔ 不静默降级（L10.1 口径，engine.py load_from 的同族先例）。
        from fermion_garden.ledger import DecisionLedger

        with self.assertRaisesRegex(ValueError, "unknown ledger operation"):
            LedgerEvent(
                sequence=1, timestamp="2026-08-21T00:00:00+00:00", operation="l124_probe",
                trace_id="t", context_version=1, item_id="a", action="keep",
                score=1.0, reason="r", criterion="c", target_role="t", budget=1,
                candidate_ids=("a",), item_source=None, item_content_sha256=None,
                conflict=None,
            )
        ledger = DecisionLedger()
        # decisions 须非空：append 逐 decision 构造 LedgerEvent（ledger.py append 的循环），
        # 空 decisions ⟹ 零构造 ⟹ 闸不触发（那条写法按构造恒过，不是验收）。
        with self.assertRaisesRegex(ValueError, "unknown ledger operation"):
            ledger.append(
                operation="l124_probe", trace_id="t", context_version=1,
                decisions=[Decision("a", "keep", 1.0, "probe")],
                criterion="c", target_role="t", budget=1,
                candidate_items=[ContextItem("a", "text a")],
            )

        import json
        import tempfile

        garden = CtxKey(sample_items())
        garden.select(task_state="timezone", target_role="fixer", budget=1, trace_id="s")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["ledger_events"][-1]["operation"] = "l124_probe"
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown ledger operation"):
                CtxKey.load_from(bad)

    def test_none_operation_refused_no_silent_morphing_l124(self) -> None:
        # L12.2 §C.4：operation=None 的静默变形封掉。现状（无闸）是 None 经 save→
        # load_from 被 event_from_dict 的 str() 读成字符串 "None" 静默入账；闸落在
        # LedgerEvent 构造点 ⟹ 写侧 None 直接拒、读侧 null 也拒（变形值照样拦）。
        with self.assertRaisesRegex(ValueError, "unknown ledger operation"):
            LedgerEvent(
                sequence=1, timestamp="2026-08-21T00:00:00+00:00", operation=None,
                trace_id="t", context_version=1, item_id="a", action="keep",
                score=1.0, reason="r", criterion="c", target_role="t", budget=1,
                candidate_ids=("a",), item_source=None, item_content_sha256=None,
                conflict=None,
            )

        import json
        import tempfile

        garden = CtxKey(sample_items())
        garden.select(task_state="timezone", target_role="fixer", budget=1, trace_id="s")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["payload"]["ledger_events"][-1]["operation"] = None
            nullified = Path(tmp) / "null.json"
            nullified.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown ledger operation"):
                CtxKey.load_from(nullified)

    def test_engine_operations_end_to_end_under_gate_l124(self) -> None:
        # 回归锁：闸不拦任何现行合法路径——record/select/compact/recall 各真实跑一遍，
        # 落账、save→load_from 往返、账面 operation 值全部照旧。
        import tempfile

        garden = CtxKey(sample_items())
        garden.select(task_state="timezone midnight", target_role="fixer", budget=1, trace_id="s")
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=1, trace_id="c")
        garden.recall("timezone normalize_offset stacktrace", budget=1, trace_id="r")
        operations = {e.operation for e in garden.ledger.events}
        self.assertEqual(operations, {"record", "select", "compact", "recall"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
            self.assertEqual(
                [e.operation for e in restored.ledger.events],
                [e.operation for e in garden.ledger.events],
            )


if __name__ == "__main__":
    unittest.main()
