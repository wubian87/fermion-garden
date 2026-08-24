from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import AgentRegistry, ContextItem, CtxKey
from fermion_garden.ledger import DecisionLedger
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

    def test_dump_load_round_trip_preserves_recall_and_ledger(self) -> None:
        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="compact")
        dumped = garden.dump()
        before_ledger = garden.ledger.to_jsonl()
        restored = CtxKey.load(dumped)
        self.assertEqual(restored.context_version, garden.context_version)
        self.assertEqual(restored.active_ids, garden.active_ids)
        self.assertEqual(restored.recoverable_ids, garden.recoverable_ids)
        self.assertEqual(restored.ledger.to_jsonl(), before_ledger)

        original_recall = garden.recall("retired timezone sign reversal", budget=1, trace_id="recall")
        restored_recall = restored.recall("retired timezone sign reversal", budget=1, trace_id="recall")
        self.assertEqual(restored_recall.to_dict(), original_recall.to_dict())
        original_fields = [
            (event.item_id, event.action, event.score, event.recall_self_score, event.recall_ratio, event.recall_threshold)
            for event in garden.ledger.events if event.operation == "recall"
        ]
        restored_fields = [
            (event.item_id, event.action, event.score, event.recall_self_score, event.recall_ratio, event.recall_threshold)
            for event in restored.ledger.events if event.operation == "recall"
        ]
        self.assertEqual(restored_fields, original_fields)

    def test_dump_load_empty_and_recoverable_only_preserve_context_version(self) -> None:
        empty = CtxKey()
        empty_round_trip = CtxKey.load(empty.dump())
        self.assertEqual(empty_round_trip.context_version, 0)
        self.assertEqual(empty_round_trip.active_ids, ())
        self.assertEqual(empty_round_trip.recoverable_ids, ())

        recoverable_only = CtxKey()
        recoverable_only._recoverable["archived"] = ContextItem(
            "archived", "long-tail recoverable context", source="test", metadata={"state": "recoverable"},
        )
        recoverable_only._version = 7
        restored = CtxKey.load(recoverable_only.dump())
        self.assertEqual(restored.context_version, 7)
        self.assertEqual(restored.active_ids, ())
        self.assertEqual(restored.recoverable_ids, ("archived",))
        self.assertEqual(restored._recoverable["archived"].metadata, {"state": "recoverable"})

    def test_dump_load_l20_recall_matches_frozen_ledger(self) -> None:
        # 发布候选：夹具自 2026-08-24 起从 l1run/ 与 l20run/ 运行目录逐字节迁入
        # tests/fixtures/（两件 sha256 与源一致），公开仓不再携带完整运行目录。
        json = __import__("json")
        fixtures = Path(__file__).resolve().parent / "fixtures"
        preset = json.loads((fixtures / "l1" / "preset.json").read_text(encoding="utf-8"))
        frozen_rows = [json.loads(line) for line in (fixtures / "l20" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        frozen_recall = [row for row in frozen_rows if row["operation"] == "recall"]
        items = [
            ContextItem(row["id"], row["text"], source=row["source"], tags=tuple(row["tags"]),
                        created_at=row["created_at"], pinned=row["pinned"])
            for row in preset["items"]
        ]
        garden = CtxKey(items)
        garden.compact(**preset["compact"], trace_id="af0f0d79d9ac453c9c8f269838e9fbf4")
        restored = CtxKey.load(garden.dump())
        restored.recall(
            preset["projection"]["trigger"], budget=preset["recall"]["budget"],
            target_role=preset["recall"]["target_role"], trace_id="d3d232b63ef040abb2946e0c3b1a9f87",
        )
        actual_recall = [event.to_dict() for event in restored.ledger.events if event.operation == "recall"]
        for row in [*frozen_recall, *actual_recall]:
            row.pop("timestamp")
            # L11.2：账新增只增字段 rule_ref（L11.3 再加 score_trace）。冻结件是 pre-L11.2 格式、
            # 没有这些键；与上面 pop("timestamp") 同理作归一化——本测试的断言主张是
            # 「recall 机制量与冻结件一致」，主张未动，只把新旧格式差异字段排除出比较。
            row.pop("rule_ref", None)
            row.pop("score_trace", None)  # L11.3 同上
            row.pop("agent_ref", None)  # L14.1 同上（存在身份归因字段，冻结件是 pre-L14.1 格式）
        self.assertEqual(actual_recall, frozen_recall)

    def test_save_load_from_round_trip_matches_dump_load(self) -> None:
        # L10.1 验收乙：save → load_from 与 dump → load 往返逐位一致（recall 四件量全同）。
        import tempfile

        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="compact")
        via_dump = CtxKey.load(garden.dump())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            via_file = CtxKey.load_from(path)
        self.assertEqual(via_file.snapshot(), via_dump.snapshot())
        self.assertEqual(via_file.snapshot(), garden.snapshot())
        self.assertEqual(via_file.ledger.to_jsonl(), via_dump.ledger.to_jsonl())

        trigger = "retired timezone sign reversal"
        live_bundle = garden.recall(trigger, budget=1, trace_id="recall")
        dump_bundle = via_dump.recall(trigger, budget=1, trace_id="recall")
        file_bundle = via_file.recall(trigger, budget=1, trace_id="recall")
        self.assertEqual(file_bundle.to_dict(), dump_bundle.to_dict())
        self.assertEqual(dump_bundle.to_dict(), live_bundle.to_dict())

        def recall_rows(engine: CtxKey) -> list[tuple[object, ...]]:
            return [
                (event.item_id, event.action, event.score,
                 event.recall_self_score, event.recall_ratio, event.recall_threshold)
                for event in engine.ledger.events if event.operation == "recall"
            ]

        self.assertEqual(recall_rows(via_file), recall_rows(via_dump))
        self.assertEqual(recall_rows(via_file), recall_rows(garden))

        with tempfile.TemporaryDirectory() as tmp:
            empty_path = Path(tmp) / "empty.json"
            CtxKey().save(empty_path)
            empty_via_file = CtxKey.load_from(empty_path)
        self.assertEqual(empty_via_file.snapshot(), CtxKey.load(CtxKey().dump()).snapshot())

    def test_save_crash_mid_write_keeps_original_intact_and_leaves_no_temp(self) -> None:
        # L10.1 验收丙：注入异常让写入中途失败 ⟹ 原文件逐字节不变、仍可 load_from，
        # 临时文件不留污染。两个注入点：写到一半（write 抛）与提交一刻（replace 抛）。
        import os
        import tempfile
        from unittest import mock

        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            original = path.read_bytes()

            newer = CtxKey(sample_items())
            newer.record([ContextItem("late", "post-crash evidence that must not appear")], reason="later")

            real_fdopen = os.fdopen

            def half_written_fdopen(fd, *args, **kwargs):
                stream = real_fdopen(fd, *args, **kwargs)

                class HalfWriter:  # 写一半就崩：真实句柄写前半段后抛异常
                    def write(self, data) -> None:
                        stream.write(data[: len(data) // 2])
                        raise OSError("injected crash mid-write")

                    def flush(self) -> None:
                        stream.flush()

                    def fileno(self) -> int:
                        return stream.fileno()

                    def __enter__(self):
                        return self

                    def __exit__(self, *exc_info) -> bool:
                        return stream.__exit__(*exc_info)

                return HalfWriter()

            with mock.patch("os.fdopen", side_effect=half_written_fdopen):
                with self.assertRaises(OSError):
                    newer.save(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([entry.name for entry in path.parent.iterdir()], [path.name])

            with mock.patch("os.replace", side_effect=OSError("injected crash before commit")):
                with self.assertRaises(OSError):
                    newer.save(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual([entry.name for entry in path.parent.iterdir()], [path.name])

            self.assertEqual(CtxKey.load_from(path).snapshot(), garden.snapshot())

    def test_rule_identity_library_and_event_refs_l112(self) -> None:
        # L11.2：8 条身份内容全在钥匙级身份库；事件只带引用；没打分的行不带身份
        # （record 占位分、空池／超预算 conflict 占位分）；真打过分的 conflict 行照常带。
        garden = CtxKey(sample_items())
        garden.select(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="s")
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="c")
        garden.recall("retired timezone sign reversal", budget=1, trace_id="r")

        identities = garden.dump()["rule_identities"]
        # L11.5：身份库按令新立 ledger-fields@1（账字段读法），引用集扩为三条——断言主张未动
        # （库含全部预期身份）。
        # L12.2 续（l125 五格裁定①，园主 2026-08-21）：库随 scan 新立 bm25-lexical@2 扩为四条，
        # 主张仍不动（预期集合跟着库扩）。先例＝1eb5aef（L11.5）把这两处断言从两条扩为三条，
        # commit message 自述「主张未动」——同款处理，非「改测试凑绿」。
        self.assertEqual(
            set(identities),
            {"bm25-lexical@1", "bm25-lexical@2", "d3-self-ratio@1", "ledger-fields@1"})
        scorer = identities["bm25-lexical@1"]
        self.assertEqual(scorer["kind"], "scorer")
        self.assertIn("parameters", scorer)   # #3 参数快照
        self.assertIn("tokenizer", scorer)    # #4 分词口径身份
        self.assertIn("numerics", scorer)     # #8 复算规约（归身份）
        gate = identities["d3-self-ratio@1"]
        self.assertEqual(gate["threshold"], DecisionLedger.RECALL_RATIO_THRESHOLD)
        self.assertIn("calibration", gate)    # #5 标定来路
        self.assertEqual(     # #6 限度自声明：三条结构化限度（单一场景／薄窗口／未跨料验证）
            {limit["kind"] for limit in gate["limits"]},
            {"calibration_scope", "window_relative_width", "cross_material_validation"},
        )

        self.assertEqual(     # record 行：0.0 是占位，不是打分 ⟹ 无身份（分叉#4 默认）
            {e.rule_ref for e in garden.ledger.events if e.operation == "record"}, {None})
        self.assertEqual(
            {e.rule_ref for e in garden.ledger.events if e.operation == "select"},
            {"bm25-lexical@1"})
        self.assertEqual(
            {e.rule_ref for e in garden.ledger.events if e.operation == "compact"},
            {"bm25-lexical@1"})
        self.assertEqual(     # #7：recall 行引用打分器＋门槛层两层
            {e.rule_ref for e in garden.ledger.events if e.operation == "recall"},
            {"bm25-lexical@1+d3-self-ratio@1"})

        bare = CtxKey()   # 空池 select：conflict 占位行，未打分 ⟹ 无身份
        bare.select(task_state="task", target_role="fixer", budget=1, trace_id="e")
        self.assertEqual([e.rule_ref for e in bare.ledger.events], [None])

        over = CtxKey(sample_items())   # 超预算 conflict（pinned+required > budget）：未打分 ⟹ 无身份
        over.compact(task_state="timezone", target_role="fixer", budget=1,
                     required_ids=("trace",), trace_id="m")
        self.assertEqual({e.rule_ref for e in over.ledger.events if e.trace_id == "m"}, {None})

        tied = CtxKey([   # cutoff-tie conflict：真打过分数 ⟹ 照常带身份（分叉#5 默认）
            ContextItem("older", "same relevant phrase", created_at=1),
            ContextItem("newer", "same relevant phrase", created_at=2),
        ])
        tied.compact(task_state="relevant phrase", target_role="fixer", budget=1, trace_id="t")
        self.assertIsNotNone(tied.ledger.events[-1].conflict)
        self.assertEqual({e.rule_ref for e in tied.ledger.events if e.trace_id == "t"},
                         {"bm25-lexical@1"})

    def test_rule_identity_roundtrip_merge_and_v1_compat_l112(self) -> None:
        # L11.2：往返保身份；pre-L11.2 的 v1 旧文件仍可载（容错读，引用为 None）；
        # 跨版本旧引用并入不断线（分叉#8 丢信息通道的唯一处，堵死）；同引用异内容拒载。
        import json
        import tempfile

        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="c")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
            self.assertEqual(restored.dump()["rule_identities"], garden.dump()["rule_identities"])
            self.assertEqual(
                [e.rule_ref for e in restored.ledger.events],
                [e.rule_ref for e in garden.ledger.events],
            )

            legacy_doc = json.loads(path.read_text(encoding="utf-8"))   # 模拟 pre-L11.2 v1 文件
            del legacy_doc["payload"]["rule_identities"]
            for row in legacy_doc["payload"]["ledger_events"]:
                row.pop("rule_ref", None)
            legacy_path = Path(tmp) / "legacy.json"
            legacy_path.write_text(json.dumps(legacy_doc, ensure_ascii=False), encoding="utf-8")
            legacy = CtxKey.load_from(legacy_path)
            self.assertEqual([e.rule_ref for e in legacy.ledger.events],
                             [None] * len(legacy.ledger.events))
            self.assertEqual(set(legacy.dump()["rule_identities"]),
                             {"bm25-lexical@1", "bm25-lexical@2", "d3-self-ratio@1", "ledger-fields@1"})  # L11.5 扩一条；L12.2 续（l125 五格裁定①）再扩 bm25-lexical@2——主张未动（先例 1eb5aef）

            older_doc = json.loads(path.read_text(encoding="utf-8"))   # scorer@0 时代旧身份并入
            older_doc["payload"]["rule_identities"]["bm25-lexical@0"] = {
                "kind": "scorer", "id": "bm25-lexical", "version": 0}
            older_path = Path(tmp) / "older.json"
            older_path.write_text(json.dumps(older_doc, ensure_ascii=False), encoding="utf-8")
            self.assertIn("bm25-lexical@0", CtxKey.load_from(older_path).dump()["rule_identities"])

            tampered = json.loads(path.read_text(encoding="utf-8"))    # 同引用异内容 ⟹ 拒载
            tampered["payload"]["rule_identities"]["bm25-lexical@1"] = {"tampered": True}
            bad_path = Path(tmp) / "bad.json"
            bad_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rule identity"):
                CtxKey.load_from(bad_path)

    def test_score_items_with_trace_matches_and_short_strings_l113(self) -> None:
        # L11.3 恒等测试。场景 C 义务（园主 2026-08-20 收窄）：料里必须含 4–5 token 端短句。
        # ⚠️ 构造属性（纪律预告兑现）：旁路内部调 score_items 拿权威分，故「traced_scores ==
        # scores」不作证据；真断言是 trace 内部自洽——rounded==score_items 终值（锁两份实现
        # 漂移）＋按身份库常数复算 idf/denominator/contribution（锁常数与字段不串）。
        import math

        from fermion_garden.lexical import score_items, score_items_with_trace

        short_items = [
            ContextItem("s1", "fix timezone midnight rollover", created_at=1),   # 4 token
            ContextItem("s2", "the csv exporter uses windows", created_at=2),    # 5 token
            ContextItem("s3", "北京时区跨午夜", created_at=3),                    # zh 单字＋bigram
        ]
        cases = [
            ("repair the timezone midnight boundary", sample_items()),
            ("retired timezone sign reversal", sample_items()),
            ("timezone midnight rollover fix", short_items),
            ("windows csv delimiter", [
                ContextItem("only", "CSV delimiter differs on Windows",
                            tags=("windows",), created_at=9),   # tags 进文档（身份库 document 口径）
            ]),
            ("nothing matches this query at all", sample_items()),
        ]
        for query, items in cases:
            scores = score_items(query, items)
            traced_scores, traces = score_items_with_trace(query, items)
            self.assertEqual(traced_scores, scores)  # 两次独立 score_items 调用结果一致（确定性）
            self.assertEqual(set(traces), {item.id for item in items})
            for item in items:
                trace = traces[item.id]
                self.assertEqual(trace["rounded"], scores[item.id])  # 漂移锁
                self.assertEqual(trace["n_docs"], len(items))
                self.assertGreater(trace["avg_len"], 0)
                total = 0.0
                for term in trace["terms"]:
                    idf = math.log((trace["n_docs"] - term["df"] + 0.5) / (term["df"] + 0.5) + 1)
                    self.assertAlmostEqual(term["idf"], idf, places=12)
                    denominator = term["tf"] + 1.5 * (0.25 + 0.75 * trace["doc_len"] / trace["avg_len"])
                    self.assertAlmostEqual(term["denominator"], denominator, places=12)
                    self.assertAlmostEqual(
                        term["contribution"],
                        term["idf"] * term["tf"] * 2.5 / term["denominator"], places=12)
                    total += term["contribution"]
                self.assertAlmostEqual(trace["unrounded_sum"], total, places=12)
        self.assertEqual(score_items_with_trace("x", []), ({}, {}))

    def test_engine_score_traces_query_identity_and_roundtrip_l113(self) -> None:
        # L11.3 端到端：trace 的 query 身份（:296 义务——self 的 query＝条目自身文本）；
        # record／占位 conflict 行无 trace；真打分的 conflict 行有；save→load_from 全量存活。
        import tempfile

        garden = CtxKey(sample_items())
        trigger = "retired timezone sign reversal"
        garden.select(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="s")
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="c")
        garden.recall(trigger, budget=1, trace_id="r")

        criterion = "target_role=fixer; task=timezone midnight"
        for event in (e for e in garden.ledger.events if e.operation in ("select", "compact")):
            self.assertEqual(event.score_trace["score"]["query"], criterion)
            self.assertEqual(event.score_trace["score"]["rounded"], event.score)
        self.assertEqual(     # record 行未打分 ⟹ 无 trace（分叉#4 默认）
            {e.score_trace for e in garden.ledger.events if e.operation == "record"}, {None})
        texts = {item.id: item.text for item in sample_items()}
        for event in (e for e in garden.ledger.events if e.operation == "recall"):
            self.assertEqual(event.score_trace["score"]["query"], trigger)  # 目标分 query＝trigger 原文
            self.assertEqual(event.score_trace["score"]["rounded"], event.score)
            self.assertEqual(event.score_trace["self"]["query"], texts[event.item_id])  # :296 义务
            self.assertEqual(event.score_trace["self"]["rounded"], event.recall_self_score)

        tied = CtxKey([   # cutoff-tie conflict：真打过分数 ⟹ trace 照常带（分叉#5 默认）
            ContextItem("older", "same relevant phrase", created_at=1),
            ContextItem("newer", "same relevant phrase", created_at=2),
        ])
        tied.compact(task_state="relevant phrase", target_role="fixer", budget=1, trace_id="t")
        self.assertTrue(all(e.score_trace is not None and e.score_trace["score"]["rounded"] == e.score
                            for e in tied.ledger.events if e.trace_id == "t"))
        bare = CtxKey()   # 空池：无打分 ⟹ 无 trace
        bare.select(task_state="task", target_role="fixer", budget=1)
        self.assertTrue(all(e.score_trace is None for e in bare.ledger.events))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            restored = CtxKey.load_from(path)
            self.assertEqual(     # 事件级 score_trace 全量存活（值＋结构）
                [(e.item_id, e.score_trace) for e in restored.ledger.events],
                [(e.item_id, e.score_trace) for e in garden.ledger.events],
            )

    def test_rule_identity_three_additions_l115(self) -> None:
        # L11.5 §A 三格（园主定死，无裁量）：① idf 对数底数写明；② pool_statistics 补 compact 格
        # （池＝打分那一刻的 active，非 compact 之后）；③ 新立 ledger-fields@1 载 item_content_sha256
        # 序列化口径。含一处行为交叉核：按口径复算指纹＝账上指纹（验「文档与代码一致」）。
        import hashlib

        garden = CtxKey([
            ContextItem("withtags", "timezone midnight", tags=("a", "b"), created_at=1),
            ContextItem("notags", "csv exporter", created_at=2),
        ])
        garden.select(task_state="timezone midnight", target_role="fixer", budget=1)
        identities = garden.dump()["rule_identities"]

        scorer = identities["bm25-lexical@1"]                      # ①
        self.assertIn("natural logarithm", scorer["parameters"]["idf"])
        self.assertIn("math.log", scorer["parameters"]["idf"])
        pool_rule = scorer["parameters"]["pool_statistics"]        # ②
        self.assertIn("compact", pool_rule)
        self.assertIn("AS OF THE SCORING MOMENT", pool_rule)
        self.assertIn("NOT the active after compact", pool_rule)

        fields = identities["ledger-fields@1"]                     # ③
        sha_spec = fields["fields"]["item_content_sha256"]
        self.assertIn("U+001F", sha_spec["separator"])
        self.assertIn("0x1f", sha_spec["separator"])
        for item in (ContextItem("t1", "timezone midnight", tags=("a", "b")),
                     ContextItem("t2", "csv exporter")):
            garden.record([ContextItem(f"{item.id}-x", item.text, tags=item.tags, created_at=9)],
                          reason="l115 sha spec check")
            event = next(e for e in garden.ledger.events if e.item_id == f"{item.id}-x")
            expected = hashlib.sha256(
                (item.text + "\x1f" + "\x1f".join(item.tags)).encode("utf-8")
            ).hexdigest()
            self.assertEqual(event.item_content_sha256, expected)   # 口径（含空 tags 仍补 SEP）⟹ 同指纹

    def test_missing_legacy_ledger_keys_refused_l114a(self) -> None:
        # L11.4a：缺老键（recall 三件套）的文件必须拒读（KeyError），⛔ 不许静默变 None。
        # 老键 to_dict 恒写（ledger.py），合法 dump 产物必带；缺 ⟹ 文件不合法 ⟹
        # fail-closed——L10.1「版本不匹配一律拒读、不静默降级」的同款地
        # （L11.2 的 c56211d 曾把这三键跟新键一起放宽成 .get，本条把闸修回）。
        import json
        import tempfile

        garden = CtxKey(sample_items())
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2, trace_id="c")
        garden.recall("retired timezone sign reversal", budget=1, trace_id="r")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            for row in document["payload"]["ledger_events"]:
                if row["operation"] == "recall":
                    del row["recall_self_score"]
                    break
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(KeyError):
                CtxKey.load_from(bad)

    def test_agent_registry_issues_fixed_width_numbers_past_full_roster_l141(self) -> None:
        # L14.1 发号：顺序唯一；第 9 个是命名意义上的 1 脑＋8 腕满编，⛔ 不是封顶。
        registry = AgentRegistry()
        numbers = [registry.register(note=f"agent-{index}") for index in range(1, 11)]
        self.assertEqual(numbers[0], "000000001")
        self.assertEqual(numbers[8], "000000009")
        self.assertEqual(numbers[9], "000000010")
        self.assertEqual(len(set(numbers)), 10)
        self.assertTrue(all(len(number) == 9 and number.isdecimal() for number in numbers))

    def test_acting_agent_rejects_non_nine_digit_values_l141(self) -> None:
        # L14.1 九位闸：构造口与换手写口同一把闸，不静默截断／补零。
        invalid = ("1", "00000001", "0000000001", "abcdefghi", "１２３４５６７８９")
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "9-digit fixed-width"):
                    CtxKey(agent=value)
        garden = CtxKey(agent="000000001")
        self.assertEqual(garden.acting_agent, "000000001")
        with self.assertRaisesRegex(ValueError, "9-digit fixed-width"):
            garden.acting_agent = "00000001"
        self.assertEqual(garden.acting_agent, "000000001")

    def test_acting_agent_stamps_record_select_scan_compact_and_recall_l141(self) -> None:
        # L14.1 盖章：record 是独立写口；其余四类动作共用 _write_bundle 写口。
        garden = CtxKey()
        agent = garden.agent_registry.register("primary worker")
        garden.acting_agent = agent
        garden.record(sample_items(), reason="initial attributed context")
        garden.select(task_state="timezone midnight", target_role="fixer", budget=2)
        garden.scan("timezone midnight", target_role="auditor")
        garden.compact(task_state="timezone midnight", target_role="fixer", budget=2)
        garden.recall("retired timezone sign reversal", budget=1)
        self.assertEqual(
            {event.operation for event in garden.ledger.events},
            {"record", "select", "scan", "compact", "recall"},
        )
        self.assertTrue(all(event.agent_ref == agent for event in garden.ledger.events))
        self.assertTrue(all(row["agent_ref"] == agent for row in garden.dump()["ledger_events"]))

    def test_agent_registry_round_trip_preserves_records_and_continues_numbering_l141(self) -> None:
        # L14.1 registry 随钥匙走；load 后从最后一个号之后续发，不复用旧号。
        garden = CtxKey()
        issued = [garden.agent_registry.register(f"agent-{index}") for index in range(1, 11)]
        restored = CtxKey.load(garden.dump())
        self.assertEqual(restored.agent_registry.to_dict(), garden.agent_registry.to_dict())
        self.assertEqual(restored.agent_registry.agents[issued[0]].note, "agent-1")
        self.assertEqual(restored.agent_registry.register("late joiner"), "000000011")

    def test_handoff_carries_both_agents_and_receiver_sets_its_own_acting_agent_l141(self) -> None:
        # L14.1 交接：钥匙写两头；load 只读回交接，不冒充接手方设置 acting_agent。
        from datetime import datetime

        garden = CtxKey()
        from_agent = garden.agent_registry.register("brain")
        to_agent = garden.agent_registry.register("arm")
        garden.acting_agent = from_agent
        dumped = garden.dump(to_agent=to_agent)
        self.assertEqual(dumped["handoff"]["from_agent"], from_agent)
        self.assertEqual(dumped["handoff"]["to_agent"], to_agent)
        self.assertIsNotNone(datetime.fromisoformat(dumped["handoff"]["at"]).tzinfo)

        receiver = CtxKey.load(dumped)
        self.assertEqual(receiver.last_handoff, dumped["handoff"])
        self.assertIsNone(receiver.acting_agent)
        receiver.acting_agent = to_agent
        receiver.record([ContextItem("received", "handoff received")], reason="continue work")
        self.assertEqual(receiver.ledger.events[-1].agent_ref, to_agent)

    def test_unattributed_and_pre_l141_events_stay_none_l141(self) -> None:
        # L14.1 零行为变：没设 acting_agent 恒 None；旧文件缺新键也只读成 None。
        garden = CtxKey(sample_items())
        garden.select(task_state="timezone midnight", target_role="fixer", budget=2)
        self.assertTrue(all(event.agent_ref is None for event in garden.ledger.events))
        dumped = garden.dump()
        self.assertNotIn("handoff", dumped)
        dumped.pop("agent_registry")
        for row in dumped["ledger_events"]:
            row.pop("agent_ref")
        restored = CtxKey.load(dumped)
        self.assertTrue(all(event.agent_ref is None for event in restored.ledger.events))
        self.assertEqual(restored.agent_registry.register("first post-upgrade agent"), "000000001")

    def test_load_from_rejects_format_version_mismatch(self) -> None:
        # L10.1 验收丁：format_version 不匹配（或缺失）⟹ 明确 ValueError，不静默降级。
        import json
        import tempfile

        garden = CtxKey(sample_items())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "garden.json"
            garden.save(path)
            document = json.loads(path.read_text(encoding="utf-8"))

            future = dict(document, format_version=document["format_version"] + 1)
            path.write_text(json.dumps(future, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "format_version mismatch"):
                CtxKey.load_from(path)

            legacy = dict(document)
            legacy.pop("format_version")
            path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "format_version"):
                CtxKey.load_from(path)

            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(CtxKey.load_from(path).snapshot(), garden.snapshot())


if __name__ == "__main__":
    unittest.main()
