from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey
from fermion_garden.lexical import SCAN_SCORER_RULE_IDENTITY, SCORER_RULE_IDENTITY


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class L126Tests(unittest.TestCase):
    # L12.3（l126 委派令）：§B 修 @2 浅拷贝的真快照锁＋闸二回环锁；§A 撤回裁定⑤ 的
    # 占位行回环锁。§A 的在内存断言在 test_scan_l125.py 的
    # test_scan_empty_pool_places_one_placeholder_row_l126（令明令重写的那条）。

    def test_at2_is_independent_deep_snapshot_of_at1_l126(self) -> None:
        # L12.3 §B：@2 构造改 copy.deepcopy（lexical.py）后的真快照锁——运行时改 @1
        # 的嵌套可变值，断言 @2 逐字节不变。四处＝spread 浅拷贝时代与 @1 共享引用的
        # 全部位置（lexical.py 注释所列）：parameters.constants／tokenizer／
        # tokenizer.rules／numerics。try/finally 现场恢复（clear+update 保住 dict
        # 对象身份，已建 CtxKey 实例的 _rule_identities 引用不断线），⛔ 不污染别的测试。
        self.assertIsNot(SCAN_SCORER_RULE_IDENTITY, SCORER_RULE_IDENTITY)
        self.assertIsNot(
            SCAN_SCORER_RULE_IDENTITY["parameters"]["constants"],
            SCORER_RULE_IDENTITY["parameters"]["constants"],
        )
        self.assertIsNot(
            SCAN_SCORER_RULE_IDENTITY["tokenizer"], SCORER_RULE_IDENTITY["tokenizer"]
        )
        self.assertIsNot(
            SCAN_SCORER_RULE_IDENTITY["tokenizer"]["rules"],
            SCORER_RULE_IDENTITY["tokenizer"]["rules"],
        )
        self.assertIsNot(SCAN_SCORER_RULE_IDENTITY["numerics"], SCORER_RULE_IDENTITY["numerics"])
        frozen_at2 = _dump(SCAN_SCORER_RULE_IDENTITY)
        at1_backup = copy.deepcopy(SCORER_RULE_IDENTITY)
        try:
            SCORER_RULE_IDENTITY["parameters"]["constants"]["tf_weight"] = 999.0
            SCORER_RULE_IDENTITY["tokenizer"]["note"] = "mutated"
            SCORER_RULE_IDENTITY["tokenizer"]["rules"].append("mutated rule")
            SCORER_RULE_IDENTITY["numerics"]["note"] = "mutated"
            # 改动真生效（防空过：若 @1 变异本身没发生，「@2 不变」会空口通过）
            self.assertNotEqual(_dump(SCORER_RULE_IDENTITY), _dump(at1_backup))
            self.assertEqual(_dump(SCAN_SCORER_RULE_IDENTITY), frozen_at2)
        finally:
            SCORER_RULE_IDENTITY.clear()
            SCORER_RULE_IDENTITY.update(copy.deepcopy(at1_backup))
        self.assertEqual(_dump(SCORER_RULE_IDENTITY), _dump(at1_backup))  # 现场已还原

    def test_at2_deepcopy_keeps_save_load_identity_gate_passing_l126(self) -> None:
        # L12.3 §B 必答的锁：deepcopy 不改值 ⟹ dump 出的 @2 payload 与现行 @2 值相等
        # ⟹ engine.py load 身份合并闸（同 ref 而 != ⟹ ValueError 拒载）放行。
        # save→load_from 回环真跑一次（⛔ 不只推理），并断言库四条全量存活、值逐键相等。
        garden = CtxKey([ContextItem("issue", "timezone boundary fails at midnight")])
        garden.scan("timezone", target_role="fixer", trace_id="l126-gate")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            restored = CtxKey.load_from(path)  # 闸二不成立则此处 ValueError ⟹ 本条红
        identities = restored.dump()["rule_identities"]
        self.assertEqual(
            set(identities),
            {"bm25-lexical@1", "bm25-lexical@2", "d3-self-ratio@1", "ledger-fields@1"},
        )
        self.assertEqual(identities["bm25-lexical@2"], SCAN_SCORER_RULE_IDENTITY)
        self.assertEqual(identities["bm25-lexical@1"], SCORER_RULE_IDENTITY)

    def test_scan_empty_pool_placeholder_row_survives_save_load_l126(self) -> None:
        # L12.3 §A 回环半边：空全池 scan 的占位行经 save→load_from 全链存活（operation
        # 闸含 scan）——「scan 跑过一次、当时全池是空的」跨进程仍可查。
        garden = CtxKey()
        garden.scan("anything at all", target_role="fixer", trace_id="l126-empty")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
        rows = [event for event in restored.ledger.events if event.operation == "scan"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].item_id, rows[0].action, rows[0].score), ("*", "retain", 0.0))
        self.assertEqual(rows[0].candidate_ids, ())
        self.assertIsNone(rows[0].rule_ref)


if __name__ == "__main__":
    unittest.main()
