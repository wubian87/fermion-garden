"""L17 · CtxKey.pin_latest 工程态保护——正式测试。

来路：L15 取证（代码条目挤出 ⟺ 工程态蒸发，4/4）＋ L16 三臂预注册验证
（pin 后三钥 35/36、主观追平、供给保持 36%）。本文件锁引擎语义：
切换、跨池、compact 强制保留、protect 账行、dump/load 往返、幂等、缺省不变。"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey


def code_items(*versions: int):
    return [ContextItem(f"代码v{v}", f"# code version {v}", source="code", created_at=v)
            for v in versions]


class PinLatestTests(unittest.TestCase):
    def test_pin_latest_pins_newest_and_unpins_older_in_active(self) -> None:
        garden = CtxKey(code_items(1, 2))
        self.assertEqual(garden.pin_latest("code"), "代码v2")
        self.assertTrue(garden._active["代码v2"].pinned)
        self.assertFalse(garden._active["代码v1"].pinned)

    def test_pin_latest_keeps_pinned_through_tight_compact(self) -> None:
        garden = CtxKey(code_items(1, 2) + [ContextItem("需求", "R", source="req", created_at=1)])
        garden.pin_latest("code")
        garden.compact(task_state="干活", target_role="executor", budget=1, trace_id="t")
        self.assertIn("代码v2", garden.active_ids)
        self.assertNotIn("代码v1", garden.active_ids)

    def test_pin_latest_reaches_recoverable_pool(self) -> None:
        garden = CtxKey(code_items(1, 2))
        garden.pin_latest("code")
        garden.compact(task_state="整理", target_role="executor", budget=1, trace_id="t")
        # v2 pinned 留活动区；v1 被挤进可恢复区
        self.assertIn("代码v2", garden.active_ids)
        self.assertIn("代码v1", garden.recoverable_ids)
        garden.record(code_items(3))
        self.assertEqual(garden.pin_latest("code"), "代码v3")
        self.assertTrue(garden._active["代码v3"].pinned)
        # 旧版在两个池里都已解除 pin（可恢复区的 v1 也要扫到）
        self.assertFalse(garden._recoverable["代码v1"].pinned)
        self.assertFalse((garden._active.get("代码v2") or garden._recoverable["代码v2"]).pinned)

    def test_pin_latest_tie_breaks_by_id(self) -> None:
        garden = CtxKey([
            ContextItem("代码vA", "a", source="code", created_at=2),
            ContextItem("代码vB", "b", source="code", created_at=2),
        ])
        self.assertEqual(garden.pin_latest("code"), "代码vB")

    def test_pin_latest_unknown_source_returns_none_and_writes_nothing(self) -> None:
        garden = CtxKey(code_items(1))
        before = len(garden.ledger.events)
        self.assertIsNone(garden.pin_latest("nope"))
        self.assertEqual(len(garden.ledger.events), before)

    def test_pin_latest_writes_protect_ledger_row(self) -> None:
        garden = CtxKey(code_items(1, 2))
        garden.pin_latest("code", trace_id="t-protect")
        protect = [e for e in garden.ledger.events if e.operation == "protect"]
        self.assertEqual(len(protect), 1)
        self.assertEqual(protect[0].item_id, "代码v2")
        self.assertEqual(protect[0].trace_id, "t-protect")
        self.assertIn("keep latest of source=code", protect[0].reason)

    def test_pin_latest_survives_dump_load_roundtrip(self) -> None:
        garden = CtxKey(code_items(1, 2) + [ContextItem("需求", "R", source="req", created_at=1)])
        garden.pin_latest("code")
        restored = CtxKey.load(garden.dump())
        self.assertTrue(restored._active["代码v2"].pinned)
        restored.compact(task_state="干活", target_role="executor", budget=1, trace_id="t")
        self.assertIn("代码v2", restored.active_ids)

    def test_pin_latest_idempotent_rerecord_flow(self) -> None:
        # L16 驱动的真实节律：每轮 record 新版 → pin_latest，12 轮后只有最新版 pinned。
        garden = CtxKey()
        for v in range(1, 13):
            garden.record(code_items(v))
            garden.pin_latest("code")
        for v in range(1, 12):
            pool = garden._active.get(f"代码v{v}") or garden._recoverable[f"代码v{v}"]
            self.assertFalse(pool.pinned, f"v{v} 应已解除 pin")
        self.assertTrue((garden._active.get("代码v12") or garden._recoverable["代码v12"]).pinned)
        garden.compact(task_state="终版", target_role="executor", budget=2, trace_id="t")
        self.assertIn("代码v12", garden.active_ids)

    def test_without_pin_latest_behavior_is_unchanged(self) -> None:
        # 缺省不调用：没有任何条目被 pin、账上没有 protect 行——
        # compact 的挤不挤出完全交给既有词面机制（L15 乙臂的蒸发条件由它产生）。
        garden = CtxKey(code_items(1, 2))
        garden.compact(task_state="整理", target_role="executor", budget=1, trace_id="t")
        self.assertTrue(all(not it.pinned for it in garden._active.values()))
        self.assertFalse(any(e.operation == "protect" for e in garden.ledger.events))


if __name__ == "__main__":
    unittest.main()
