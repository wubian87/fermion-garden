from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey
from fermion_garden.lexical import (
    SCAN_SCORER_RULE_IDENTITY,
    SCAN_SCORER_RULE_REF,
    SCORER_RULE_IDENTITY,
    SCORER_RULE_REF,
    score_items_with_trace,
)


def sample_items() -> list[ContextItem]:
    return [
        ContextItem("issue", "timezone boundary fails at midnight", pinned=True, created_at=1),
        ContextItem("trace", "timezone normalize_offset stacktrace", created_at=2),
        ContextItem("contract", "preserve ISO offset formatting", created_at=3),
        ContextItem("old", "retired timezone sign reversal hypothesis", created_at=4),
        ContextItem("noise", "CSV delimiter differs on Windows", created_at=5),
    ]


# l125 委派令 §3 点名锁的冻结件：bm25-lexical@1 的 payload＝d7bd7e0 时原物（由
# `git show d7bd7e0:src/fermion_garden/lexical.py` 的模块原物导出 JSON，非手抄）。
# 逐字节锁的实现：JSON 反解后与运行时 SCORER_RULE_IDENTITY 深比较——任何一处字面
# （公式描述、常数、分词规则、pool_statistics 全文）变动 ⟹ 本条红。
_AT1_FROZEN_JSON = """
{
 "kind": "scorer",
 "id": "bm25-lexical",
 "version": 1,
 "version_scope": "scoring rules only; independent of package __version__ and disk _format_version",
 "parameters": {
  "score": "sum over matched query tokens of idf * tf * 2.5 / denominator",
  "idf": "ln((n_docs - df + 0.5) / (df + 0.5) + 1); ln = natural logarithm, base e (python math.log)",
  "denominator": "tf + 1.5 * (0.25 + 0.75 * doc_len / avg_len)",
  "constants": {
   "tf_weight": 2.5,
   "length_k1": 1.5,
   "b_min": 0.25,
   "b_slope": 0.75
  },
  "document": "tokens of (text + ' ' + ' '.join(tags))",
  "query": "set(tokenize(query))",
  "pool_statistics": "df / avg_len computed on the scored pool only (select: active; compact: the active AS OF THE SCORING MOMENT — compact reuses select's single scoring pass via preview, which runs BEFORE any eviction, so the pool is the pre-compact active, NOT the active after compact; recall: recoverable)"
 },
 "tokenizer": {
  "id": "en-lower+zh-unigram+adjacent-bigram",
  "rules": [
   "ascii runs [A-Za-z0-9_]+ lowercased",
   "cjk runs -> unigrams + adjacent bigrams",
   "bigrams never cross segment gaps"
  ]
 },
 "numerics": {
  "float": "python float64",
  "final_rounding_decimals": 8,
  "json_allow_nan": false
 }
}
"""


class ScanTests(unittest.TestCase):
    # L12.2 续（l125）· §C 十项测试的产品仓部分（照 l123run/报告.md §D.3；四池回归靶
    # #1/#2 在种子园 l125run/ 回归四池.py——池数据 l121run/条目/ 不在产品仓）。
    # 逐条「按构造能不能不失败」的答案在 l125run/报告.md §C。

    def test_scan_rank_and_scores_match_raw_trigger_scorer_l125(self) -> None:
        # §C#1/#2 的产品仓小样：scan decisions 的顺序与分数＝对同一池直接跑
        # score_items_with_trace(trigger 原文) 的全排名（同一打分入口、同一排序键、零随机源
        # ⟹ 恒等式成分；四池大靶在 l125run/）。判别力：池里放了含 "fixer"/"task" 字面的
        # 陷阱条目——若实现把 query 滑回 select 拼壳串（拼壳 token 含 fixer/task），该条
        # 分数必变 ⟹ 必红（l123run 分辨率 a 同机理：大池换拼壳各恰 1 条分变）。
        pool = [
            *sample_items(),
            ContextItem("shelltrap", "the fixer logged this task", created_at=6),
        ]
        garden = CtxKey(pool)
        trigger = "timezone midnight"
        bundle = garden.scan(trigger, target_role="fixer")
        scores, _ = score_items_with_trace(trigger, pool)
        expected = sorted(pool, key=lambda item: (-scores[item.id], -item.created_at, item.id))
        self.assertEqual(
            [decision.item_id for decision in bundle.decisions],
            [item.id for item in expected],
        )
        self.assertEqual(
            [decision.score for decision in bundle.decisions],
            [scores[item.id] for item in expected],
        )

    def test_scan_ledger_rows_operation_action_rule_ref_l125(self) -> None:
        # §C#3：落账 operation="scan"（写成 select 必红）＋闸放行（LEDGER_OPERATIONS 已含
        # scan）。裁定④：动作词全 retain。裁定①：scan 行指 bm25-lexical@2，而 select／
        # compact／recall 的事件引用仍是 @1（库扩 @2 零波及旧操作）——两侧同锁。
        garden = CtxKey(sample_items())
        garden.scan("timezone midnight", target_role="fixer", trace_id="sc")
        rows = [event for event in garden.ledger.events if event.trace_id == "sc"]
        self.assertEqual(len(rows), 5)  # 全池逐条：5 条目 ⟹ 恰 5 行
        self.assertEqual({event.operation for event in rows}, {"scan"})
        self.assertEqual({event.action for event in rows}, {"retain"})
        self.assertEqual(SCAN_SCORER_RULE_REF, "bm25-lexical@2")
        self.assertEqual({event.rule_ref for event in rows}, {SCAN_SCORER_RULE_REF})

        garden.select(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="s")
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="c")
        garden.recall("retired timezone sign reversal", budget=1, trace_id="r")
        self.assertEqual(
            {e.rule_ref for e in garden.ledger.events if e.operation == "select"},
            {SCORER_RULE_REF})
        self.assertEqual(
            {e.rule_ref for e in garden.ledger.events if e.operation == "compact"},
            {SCORER_RULE_REF})
        self.assertEqual(  # recall 两层引用照旧（L11.2 #7），@2 不进旧操作
            {e.rule_ref for e in garden.ledger.events if e.operation == "recall"},
            {SCORER_RULE_REF + "+d3-self-ratio@1"})

    def test_scan_zero_state_change_l125(self) -> None:
        # §C#4：零状态锁——context_version／active_ids／recoverable_ids 调用前后逐位相等，
        # 账事件数恰增全池条数（每条目一行 retain）。误改状态必红。
        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        version_before = garden.context_version
        active_before = garden.active_ids
        recoverable_before = garden.recoverable_ids
        events_before = len(garden.ledger.events)
        pool_size = len(active_before) + len(recoverable_before)
        bundle = garden.scan("timezone midnight", target_role="fixer")
        self.assertEqual(garden.context_version, version_before)
        self.assertEqual(garden.active_ids, active_before)
        self.assertEqual(garden.recoverable_ids, recoverable_before)
        self.assertEqual(len(garden.ledger.events), events_before + pool_size)
        self.assertEqual(bundle.context_version, version_before)  # 版本 ⛔ 不 +1
        self.assertEqual(len(bundle.decisions), pool_size)

    def test_scan_pool_covers_active_union_recoverable_l125(self) -> None:
        # §C#5：record→compact→scan ⟹ decisions 覆盖 active∪recoverable 全体（被 compact
        # 的条目有行有分）。池＝active-only 的错实现 ⟹ 被压条目缺行 ⟹ 必红。
        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        self.assertTrue(garden.recoverable_ids)
        bundle = garden.scan("timezone midnight", target_role="fixer")
        covered = [decision.item_id for decision in bundle.decisions]
        self.assertEqual(set(covered), set(garden.active_ids) | set(garden.recoverable_ids))
        self.assertEqual(len(covered), len(set(covered)))  # 全池恰好各一行，无重复
        n_docs_set = {trace["score"]["n_docs"] for trace in bundle.score_traces.values()}
        self.assertEqual(n_docs_set, {len(covered)})  # n_docs＝全池条数（§C#6 成分）

    def test_scan_score_traces_query_raw_trigger_and_n_docs_l125(self) -> None:
        # §C#6：每行 trace 的 query＝trigger 原文（⛔ 不 strip、⛔ 不拼壳）＋n_docs＝池条数。
        # 判别力：query 口径错 ⟹ query 字段直读必红；池大小错 ⟹ n_docs 直读必红。
        garden = CtxKey(sample_items())
        trigger = "  timezone midnight  "
        bundle = garden.scan(trigger, target_role="fixer", trace_id="s6")
        self.assertEqual(bundle.criterion, "timezone midnight")  # 裁定②：criterion=strip 值
        pool_size = len(garden.active_ids) + len(garden.recoverable_ids)
        for item_id, trace in bundle.score_traces.items():
            self.assertEqual(trace["score"]["query"], trigger)
            self.assertEqual(trace["score"]["n_docs"], pool_size)
        for event in (e for e in garden.ledger.events if e.trace_id == "s6"):
            self.assertEqual(event.score_trace["score"]["query"], trigger)
            self.assertEqual(event.score_trace["score"]["n_docs"], pool_size)
            self.assertEqual(event.score_trace["score"]["rounded"], event.score)

    def test_scan_empty_pool_places_one_placeholder_row_l126(self) -> None:
        # §C#7 重写（裁定⑤ 2026-08-21 撤回，L12.3；本条原是 l125 落的
        # test_scan_empty_pool_normal_bundle_no_placeholder_l125）：空全池 ⟹ 正常 bundle
        # ＋恰一条占位 Decision——账上必须有一行可查。撤回来路：原注释那句
        # 「decisions 空 ⟹ ledger.append 零构造 ⟹ 账零行入账（空表本身就是忠实记录）」
        # 前提是假的——账零行 ⟹ 「scan 跑过一次、当时全池是空的」在账上查不到，撞种子 y
        # 的后半句（每一步为什么这么决定，交得出去、查得清）。占位行照 recall 空池先例
        # （engine.py 的 Decision("*", "retain", 0.0, ...)）；reason 说 scan 自己的语义
        # （没有东西可排，⛔ 非 recall 的「没捞到」）。没打过任何分 ⟹ rule_ref=None／
        # score_traces=None（照 recall 空池先例）；budget=0（len(pool)，空池恰为 0）。
        garden = CtxKey()
        bundle = garden.scan("anything at all", target_role="fixer", trace_id="s7")
        self.assertEqual(bundle.operation, "scan")
        self.assertIsNone(bundle.conflict)
        self.assertEqual(len(bundle.decisions), 1)  # 恰一条占位，⛔ 不多
        self.assertEqual(
            (bundle.decisions[0].item_id, bundle.decisions[0].action, bundle.decisions[0].score),
            ("*", "retain", 0.0),
        )
        self.assertEqual(
            bundle.decisions[0].reason, "full pool is empty: zero items to rank; no state changed"
        )
        self.assertEqual(bundle.selected_ids, ())
        self.assertEqual(bundle.evicted_ids, ())
        self.assertEqual(bundle.recalled_ids, ())
        self.assertEqual(bundle.budget, 0)
        self.assertIsNone(bundle.rule_ref)
        self.assertIsNone(bundle.score_traces)
        self.assertEqual(bundle.criterion, "anything at all")
        self.assertEqual(bundle.context_version, 0)
        self.assertEqual(garden.context_version, 0)
        self.assertEqual(len(garden.ledger.events), 1)  # 恰一行入账
        row = garden.ledger.events[0]
        self.assertEqual(row.trace_id, "s7")
        self.assertEqual((row.item_id, row.action, row.score), ("*", "retain", 0.0))
        self.assertEqual(row.candidate_ids, ())  # 空池 ⟹ 候选集空
        self.assertIsNone(row.item_source)
        self.assertIsNone(row.item_content_sha256)
        self.assertIsNone(row.rule_ref)
        self.assertIsNone(row.score_trace)

    def test_scan_blank_trigger_or_role_rejected_l125(self) -> None:
        # fail-closed 同款（recall 经 _validate_request 的同两支；scan 无 budget 入参 ⟹
        # 校验只取前两支）。拒绝时不落任何账、不动状态。
        garden = CtxKey(sample_items())
        before = garden.snapshot()
        with self.assertRaises(ValueError):
            garden.scan("   ", target_role="fixer")
        with self.assertRaises(ValueError):
            garden.scan("timezone", target_role="  ")
        self.assertEqual(before, garden.snapshot())

    def test_scan_events_survive_save_load_roundtrip_l125(self) -> None:
        # §C#3 读侧半边：scan 行经 save→load_from 全链过闸不炸、逐位存活（operation／
        # rule_ref／score_trace）。闸值域漏 scan ⟹ 本条在恢复链上逐行 ValueError ⟹ 必红。
        import tempfile

        garden = CtxKey(sample_items())
        garden.scan("timezone midnight", target_role="fixer", trace_id="sc")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
        original = [e for e in garden.ledger.events if e.trace_id == "sc"]
        recovered = [e for e in restored.ledger.events if e.trace_id == "sc"]
        self.assertEqual(
            [(e.item_id, e.operation, e.action, e.score, e.rule_ref, e.score_trace) for e in recovered],
            [(e.item_id, e.operation, e.action, e.score, e.rule_ref, e.score_trace) for e in original],
        )

    def test_bm25_lexical_at1_payload_frozen_l125(self) -> None:
        # l125 委派令 §3 点名锁：bm25-lexical@1 的 payload 与 d7bd7e0 时逐字节相同
        # （冻结件由 d7bd7e0 原物导出，见文件头 _AT1_FROZEN_JSON 注释）。
        self.assertEqual(SCORER_RULE_IDENTITY, json.loads(_AT1_FROZEN_JSON))
        self.assertEqual(SCORER_RULE_REF, "bm25-lexical@1")

    def test_bm25_lexical_at2_extends_at1_only_by_scan_pool_and_version_l125(self) -> None:
        # 裁定①的构造锁：@2＝@1 逐键相同，唯二差异＝version（1→2）与 pool_statistics
        # 尾部追加 scan 格（池＝active ∪ recoverable）。@1 文本一字不动由此与冻结锁双证。
        self.assertEqual(SCAN_SCORER_RULE_IDENTITY["version"], 2)
        self.assertEqual(
            {k: v for k, v in SCAN_SCORER_RULE_IDENTITY.items() if k not in ("version", "parameters")},
            {k: v for k, v in SCORER_RULE_IDENTITY.items() if k not in ("version", "parameters")},
        )
        at1_params = SCORER_RULE_IDENTITY["parameters"]
        at2_params = SCAN_SCORER_RULE_IDENTITY["parameters"]
        self.assertEqual(
            {k: v for k, v in at2_params.items() if k != "pool_statistics"},
            {k: v for k, v in at1_params.items() if k != "pool_statistics"},
        )
        self.assertTrue(at2_params["pool_statistics"].startswith(at1_params["pool_statistics"]))
        tail = at2_params["pool_statistics"][len(at1_params["pool_statistics"]):]
        self.assertIn("scan", tail)
        self.assertIn("active", tail)
        self.assertIn("recoverable", tail)
        # 钥匙级身份库恰四条（与 tests/test_engine.py 两处扩容断言同主张）
        self.assertEqual(
            set(CtxKey().dump()["rule_identities"]),
            {"bm25-lexical@1", "bm25-lexical@2", "d3-self-ratio@1", "ledger-fields@1"},
        )


if __name__ == "__main__":
    unittest.main()
