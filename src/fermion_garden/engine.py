"""Reversible context selection engine.

The scorer is deliberately simple and offline. It is a baseline implementation,
not a claim that lexical relevance solves multi-agent context management.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from datetime import datetime, timezone
import uuid

from .agents import AgentRegistry, is_agent_ref
from .ledger import DecisionLedger
from .lexical import (
    SCAN_SCORER_RULE_IDENTITY,
    SCAN_SCORER_RULE_REF,
    SCORER_RULE_IDENTITY,
    SCORER_RULE_REF,
    score_items_with_trace,
)
from .models import ContextBundle, ContextItem, Decision


class CtxKey:
    """Maintain active and recoverable context with an append-only decision ledger."""

    def __init__(self, items: Iterable[ContextItem] = (), *, agent: str | None = None) -> None:
        self._active: OrderedDict[str, ContextItem] = OrderedDict()
        self._recoverable: OrderedDict[str, ContextItem] = OrderedDict()
        self._version = 0
        self.ledger = DecisionLedger()
        # L14.1 存在身份（园主 2026-08-24 批「落」；设计正身＝母库 220 注 结果.md）：
        # acting_agent＝当前干活那个存在的号（账行 agent_ref 的唯一来源），None＝未归因
        # （零行为变，与 L14.1 之前完全一致）；号由 AgentRegistry 唯一发放，⛔ 不收手造号。
        self._agent = self._validated_agent(agent)
        # 存在身份注册处：钥匙级一份（同 L11.2 分叉#8 形状），随 dump/load 往返，
        # load 后续号接着发（跨会话同一存在保同号）。
        self.agent_registry = AgentRegistry()
        # 最近一次交接的两头（dump(to_agent=...) 写入、load 读回）。None＝从未交接。
        # ⚠️ load 不恢复 _agent：接手方是谁由接手方自己设（acting_agent），不藏在钥匙里。
        self.last_handoff: dict[str, str | None] | None = None
        # L11.2 规则身份库（l112run 分叉#8 默认：钥匙级一份＋事件引用）。
        # 含当前代码的两条身份（打分器／门槛层）；dump 全量带出，load 与载入身份合并
        # （旧版本引用不断线，见 load 的合并块）。⛔ 不是文件版本：不落 save 顶层、
        # 与 context_version／_format_version／__version__ 各管一事（l111run/报告.md §①#2）。
        self._rule_identities: dict[str, dict[str, object]] = {
            SCORER_RULE_REF: SCORER_RULE_IDENTITY,
            DecisionLedger.RECALL_GATE_RULE_REF: DecisionLedger.RECALL_GATE_IDENTITY,
            # L11.5 §A③：账字段读法身份（item_content_sha256 序列化口径等），园主定死新立一条、
            # 不塞进 bm25-lexical@1。
            DecisionLedger.LEDGER_FIELDS_RULE_REF: DecisionLedger.LEDGER_FIELDS_IDENTITY,
            # L12.2 续（l125 五格裁定①，园主 2026-08-21 落刀）：scan 行的身份——scan 的打分池
            # 是 active ∪ recoverable 全池，与 @1 载的 select/compact/recall 池口径不同 ⟹ 新立
            # @2 入库（构造见 lexical.py）。@1 文本一字不动；select/compact/recall 的事件引用
            # 仍是 @1，scan 行指 @2。
            SCAN_SCORER_RULE_REF: SCAN_SCORER_RULE_IDENTITY,
        }
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

    # ── L14.1 存在身份：acting_agent 的读写口（写口设 9 位闸，⛔ 不静默收破号） ──
    @staticmethod
    def _validated_agent(agent: str | None) -> str | None:
        if agent is not None and not is_agent_ref(agent):
            raise ValueError(
                f"acting agent {agent!r} is not a 9-digit fixed-width agent number; "
                "numbers are issued by AgentRegistry.register()"
            )
        return agent

    @property
    def acting_agent(self) -> str | None:
        return self._agent

    @acting_agent.setter
    def acting_agent(self, agent: str | None) -> None:
        self._agent = self._validated_agent(agent)

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
            agent_ref=self._agent,  # L14.1：这一步是哪个存在干的（None＝未归因，旧口径）
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

        # L11.3 甲路·调用点一（select；compact 经 _plan_select 复用这一次打分，一处改两操作
        # 受益——l112run 分叉#6「记一份，compact 沿用」）。分数仍由 score_items 权威给出
        # （score_items_with_trace 内部就是那次调用，分数路径零改动），traces 旁出逐 token
        # 推导；query 嵌打分原文——criterion 即打分串（:124），事件自含、接手方可复算。
        scores, score_traces, ranked = self._score_and_rank(criterion, self._active.values())
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
                # L11.2：这条 conflict 路径真打过分数（scores 来自 score_items）——有分就有身份
                # （l112run 分叉#5 默认）。
                rule_ref=SCORER_RULE_REF,
                # L11.3：同上——真打过分的 conflict 行，trace 照常带（分叉#5 默认）。
                score_traces=score_traces,
            )
            return bundle
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
            rule_ref=SCORER_RULE_REF,  # L11.2：正常打分路径的身份引用（l111run/报告.md §①#1）
            score_traces=score_traces,  # L11.3：同一旁路产出的逐 item 推导
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
                rule_ref=preview.rule_ref,  # L11.2：沿用 preview 的身份引用（l112run 分叉#6：记一份、compact 沿用）
                score_traces=preview.score_traces,  # L11.3：同款沿用——preview 打的分与推导，compact 不重算
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
            rule_ref=preview.rule_ref,  # L11.2：与 score_by_id 同款——preview 打的分，compact 沿用其身份
            score_traces=preview.score_traces,  # L11.3：与 score_by_id 同款——分与推导都沿用，不重算
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
        pool = list(self._recoverable.values())
        # L11.3 甲路·调用点二（recall 目标分）：分数路径零改动（旁路内部就是 score_items 那次调用）；
        # query 嵌 trigger 原文——下方 criterion 落账的是 trigger.strip()，与打分原文不是同一个串，
        # 嵌原文消歧（l111run/报告.md §②甲）。
        scores, raw_target_traces = score_items_with_trace(trigger, pool)
        # L2.0 · D3 逐条自碰归一化：分母 self(i) ＝ 条目 i 拿自己的文本当 query 在同一可恢复池上
        # 对自己的分（满分刻度，与分子同池同统计 ⟹ 池大小带来的 IDF 系统偏差在比值里约掉）。
        # 召回条件 ratio(i) = score_T(i) / self(i) ≥ DecisionLedger.RECALL_RATIO_THRESHOLD；
        # 排序仍按分数（口径未动）。成本：每次 recall 多 |pool| 次全池打分（O(|pool|²)，本地）。
        # L11.3 甲路·调用点三（recall 自分）：保持原 per-item 全池打分形状（每个 item 各跑一次
        # 全量打分再取一值，O(|pool|²) 评分不变——构造推导，非新增成本）；每条留存 trace 的
        # query 嵌该条目自身文本——|pool| 条 self-trace 必须各带 query 身份，否则分不清出自
        # 哪次打分（l111run/报告.md §②甲-2 对 :296 的独有义务）。
        self_scores: dict[str, float] = {}
        self_traces: dict[str, dict[str, object]] = {}
        for item in pool:
            per_item_scores, per_item_traces = score_items_with_trace(item.text, pool)
            self_scores[item.id] = per_item_scores[item.id]
            self_traces[item.id] = per_item_traces[item.id]
        ratios: dict[str, float] = {}
        for item in pool:
            # 边界处置（进账，⛔ 不静默跳过）：self(i)==0（如条目 tokenize 后为空，本无从量刻度）
            # ⟹ 比值定义为 0.0 ⟹ 必不召回；该行的 reason 会写明这一处置。
            ratios[item.id] = scores[item.id] / self_scores[item.id] if self_scores[item.id] > 0 else 0.0
        threshold = DecisionLedger.RECALL_RATIO_THRESHOLD
        ranked = sorted(
            pool,
            key=lambda item: (-scores[item.id], -item.created_at, item.id),
        )
        recalled = tuple(item.id for item in ranked if ratios[item.id] >= threshold)[:budget]
        if recalled:
            self._version += 1
            for item_id in recalled:
                self._active[item_id] = self._recoverable.pop(item_id)
        decisions = tuple(
            Decision(
                item.id,
                "recall" if item.id in recalled else "retain",
                scores[item.id],
                (
                    "matched recall trigger" if item.id in recalled else
                    ("self_score=0 (no lexical scale): ratio defined as 0; not recalled"
                     if self_scores[item.id] <= 0 else "not recalled for this trigger")
                ),
            )
            for item in ranked
        )
        if not decisions:
            decisions = (Decision("*", "retain", 0.0, "no recoverable context matched trigger"),)
        # L11.2（l111run/报告.md §①#7）：recall 行的规则是两层——打分器＋D3 门槛层，
        # 事件引用两层都带；空池时没打过任何分，引用为 None（与 record 行的占位分同理）。
        recall_rule_ref = (
            f"{SCORER_RULE_REF}+{DecisionLedger.RECALL_GATE_RULE_REF}" if pool else None
        )
        # L11.3：recall 行的 trace 两层——score（query＝trigger 原文）＋self（query＝该条目文本）；
        # 空池时无任何打分，整体为 None。
        recall_score_traces: dict[str, dict[str, object]] | None = None
        if pool:
            recall_score_traces = {
                item.id: {
                    "score": {"query": trigger, **raw_target_traces[item.id]},
                    "self": {"query": item.text, **self_traces[item.id]},
                }
                for item in pool
            }
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
            rule_ref=recall_rule_ref,
            score_traces=recall_score_traces,
        )
        self._write_bundle(
            bundle,
            recall_self_scores=self_scores,
            recall_ratios=ratios,
            recall_threshold=threshold,
        )
        return bundle

    # ── L12.2 §B（l125 委派令落码）：全池排名表。零状态改动、只落账；纯打分一次、全量排名，
    # 无 conflict 闸、无 mandatory、无 required_ids（L12.0 实测口径，l121run/报告.md §C）。
    # 十格填法照 l125 委派令 §2 逐格定死（含五格裁定）；可推翻格未推翻，见 l125run/报告.md。──
    def scan(
        self,
        trigger: str,
        *,
        target_role: str = "unspecified",
        trace_id: str | None = None,
    ) -> ContextBundle:
        # 五格裁定③：target_role 带默认 "unspecified"（recall 先例），⛔ 不学 select 必填。
        # 校验取 recall 口径（经 _validate_request 的前两支：criterion／target_role 非空）；
        # scan 无 budget 入参（§B 全量排名无截断）⟹ budget 支不适用，⛔ 不为凑调用造预算值。
        if not trigger.strip():
            raise ValueError("criterion/task state must not be blank")
        if not target_role.strip():
            raise ValueError("target_role must not be blank")
        trace = trace_id or self._trace_id()
        # §B.1：池＝active ∪ recoverable 全池，active 在前、recoverable 在后（同 _write_bundle
        # 的 candidate_items 拼接序）。§B.2：打分 query＝trigger 原文——⛔ 不拼壳、⛔ 不 strip
        # （账面 criterion 落的才是 strip 后的串，两个串不同，trace 嵌原文消歧，同 recall 先例）。
        pool = [*self._active.values(), *self._recoverable.values()]
        scores, score_traces, ranked = self._score_and_rank(trigger, pool)
        # §B 十格：decisions＝按名次序的全池逐条，排名表整个放这里（不选、不逐、不捞）。
        # 动作词沿用 retain（五格裁定④）：retain 语义正是「没动它」，scan 零状态改动；
        # ⛔ 不加新词、⛔ 不动 models.py 的 Action 值域。
        decisions = tuple(
            Decision(
                item.id, "retain", scores[item.id],
                "ranked in full-pool scan; no state changed",
            )
            for item in ranked
        )
        # 裁定⑤ 撤回（园主 2026-08-21 落刀「落」，L12.3）：空全池 ⟹ 落一条占位 Decision——
        # 账上必须有一行可查。来路：原裁定「空表本身就是忠实记录」被实测打掉——空全池 scan
        # 在账上零行 ⟹ 「scan 跑过一次、当时全池是空的」在账上查不到，撞种子 y 的后半句
        # （每一步为什么这么决定，交得出去、查得清）。形状照 recall 空池先例（上方 recall 的
        # 占位行）；reason 说 scan 自己的语义——不是「没捞到」，是「没有东西可排」。
        if not decisions:
            decisions = (
                Decision("*", "retain", 0.0, "full pool is empty: zero items to rank; no state changed"),
            )
        # 空池没打过任何分 ⟹ 身份引用与推导为 None（照 recall 空池先例；裁定⑤ 撤回不改这
        # 一格）。budget=len(pool)（l125 提刀：忠实表达全量排名无截断，空池恰为 0）。
        bundle = ContextBundle(
            operation="scan",
            criterion=trigger.strip(),  # 五格裁定②：照 recall 先例落 strip 值，⛔ 不走拼壳
            target_role=target_role,
            selected_ids=(),
            evicted_ids=(),
            recalled_ids=(),
            decisions=decisions,
            context_version=self._version,  # §B.4 零状态改动：版本 ⛔ 不 +1
            trace_id=trace,
            budget=len(pool),
            rule_ref=SCAN_SCORER_RULE_REF if pool else None,  # 裁定①：scan 行指 @2
            score_traces=score_traces if pool else None,
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

    def dump(self, to_agent: str | None = None) -> dict[str, object]:
        """Return the complete in-memory context as an auditable JSON value.

        L14.1: ``to_agent`` 给出时，钥匙上写明这次交接的两头（from_agent／to_agent）；
        缺省 None ⟹ 钥匙不带 handoff 块，与 L14.1 之前逐字节同形（零行为变）。
        """
        # L9.1 / l91run-v4：K=1/2/3（主口径还含K=6）的复现风险低于位置置换带，
        # 但K=14/15真实风险集仍有22/6个、随机下常连一个也没有。可恢复擦除的价值
        # 因而在长尾；_recoverable 目前只是进程内 OrderedDict，必须可审计地序列化。
        # JSON 而非 pickle：状态要可读、可查，不能把审计交给不可读的执行载荷。
        import json

        def item_to_dict(item: ContextItem) -> dict[str, object]:
            return {
                "id": item.id,
                "text": item.text,
                "source": item.source,
                "tags": list(item.tags),
                "created_at": item.created_at,
                "pinned": item.pinned,
                "metadata": dict(item.metadata),
            }

        payload: dict[str, object] = {
            "active": [item_to_dict(item) for item in self._active.values()],
            "recoverable": [item_to_dict(item) for item in self._recoverable.values()],
            "context_version": self._version,
            "ledger_events": [event.to_dict() for event in self.ledger.events],
            # L11.2 规则身份库：钥匙级一份（全量），事件只带 rule_ref 引用（l112run 分叉#8 默认）。
            "rule_identities": self._rule_identities,
            # L14.1 存在身份注册处：钥匙级一份（同款形状），账行只带 agent_ref 引用；
            # 事件引用的解析口随钥匙走，跨会话续号不断线。
            "agent_registry": self.agent_registry.to_dict(),
        }
        if to_agent is not None:
            payload["handoff"] = {
                "from_agent": self._agent,
                "to_agent": self._validated_agent(to_agent),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        # Round-trip through the standard JSON codec proves the returned value is JSON, not pickle-shaped state.
        return json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))

    @classmethod
    def load(cls, dumped: dict[str, object]) -> CtxKey:
        """Restore a CtxKey previously emitted by :meth:`dump` without writing a ledger event."""
        from .ledger import LedgerEvent

        def item_from_dict(row: dict[str, object]) -> ContextItem:
            return ContextItem(
                str(row["id"]),
                str(row["text"]),
                source=str(row["source"]),
                tags=tuple(str(tag) for tag in row["tags"]),
                created_at=int(row["created_at"]),
                pinned=bool(row["pinned"]),
                metadata=dict(row["metadata"]),
            )

        def event_from_dict(row: dict[str, object]) -> LedgerEvent:
            return LedgerEvent(
                sequence=int(row["sequence"]), timestamp=str(row["timestamp"]), operation=str(row["operation"]),
                trace_id=str(row["trace_id"]), context_version=int(row["context_version"]), item_id=str(row["item_id"]),
                action=str(row["action"]), score=float(row["score"]), reason=str(row["reason"]),
                criterion=str(row["criterion"]), target_role=str(row["target_role"]), budget=row["budget"],
                candidate_ids=tuple(str(item_id) for item_id in row["candidate_ids"]), item_source=row["item_source"],
                item_content_sha256=row["item_content_sha256"], conflict=row["conflict"],
                # L11.4a：三个老键改回严格读。来路：L11.2 commit（c56211d）把它们跟着新键
                # 一起放宽成了 .get——但这三个键 to_dict 恒写（ledger.py），dump() 产出的
                # 合法文件必带 ⟹ 不需要容错；而这块地立过反向纪律：L10.1 的 load_from
                # 「版本不匹配一律 ValueError 拒读，⛔ 不静默降级」。放宽的作用域比它要解决
                # 的问题大了：需要 fail-open 的只有下面 L11.2/L11.3 的新键（老文件没记过）。
                # 缺老键 ⟹ 文件不合法 ⟹ 拒读（KeyError），⛔ 不静默变 None。
                recall_self_score=row["recall_self_score"], recall_ratio=row["recall_ratio"],
                recall_threshold=row["recall_threshold"],
                # L11.2：v1 内新增的只增字段用容错读——pre-L11.2 的 v1 旧文件没有此键，
                # 缺键的语义就是「当时没记」（None），与 record 行占位分同款；
                # 新写文件此键恒在（to_dict 恒写）。
                rule_ref=row.get("rule_ref"),
                # L11.3：同上（pre-L11.3 的 v1 文件无此键 ⟹ None＝当时没记推导）。
                score_trace=row.get("score_trace"),
                # L14.1：同上（pre-L14.1 的文件无此键 ⟹ None＝当时未归因）。
                agent_ref=row.get("agent_ref"),
            )

        restored = cls()
        active = [item_from_dict(row) for row in dumped["active"]]
        recoverable = [item_from_dict(row) for row in dumped["recoverable"]]
        restored._active = OrderedDict((item.id, item) for item in active)
        restored._recoverable = OrderedDict((item.id, item) for item in recoverable)
        restored._version = int(dumped["context_version"])
        restored.ledger._events = [event_from_dict(row) for row in dumped["ledger_events"]]
        # L11.2 身份库合并：当前代码身份为底（restored 由 cls() 新建，已含两条现行身份），
        # 载入身份并入。分叉#8「钥匙级一份＋事件引用」的唯一丢信息通道是「跨版本旧引用」
        # ——文件里 scorer@0 时代的身份并入后，旧事件的引用仍可解析，通道堵死。
        # 同引用不同内容 ＝ 改了规则没 bump 版本 ⟹ 拒载，⛔ 不静默降级（同 load_from 版本口径）。
        for ref, payload in dumped.get("rule_identities", {}).items():
            if ref in restored._rule_identities and restored._rule_identities[ref] != payload:
                raise ValueError(
                    f"rule identity {ref!r} in file differs from current code; refusing to load"
                )
            restored._rule_identities[ref] = payload
        # L14.1 存在身份注册处：随钥匙走、load 后续号接着发。容错读——pre-L14.1 的
        # 旧文件没有此键 ⟹ 空 registry 从 1 起发（旧账 agent_ref 恒 None，无引用可解析）。
        # ⚠️ 与 rule_identities 的「合并」不同语义：registry 是登记数据不是代码身份，
        # 文件里的登记表整体取代（同 ledger_events 的读法）。_agent 不从文件恢复——
        # 接手方自己设 acting_agent；只读回最近一次交接的两头供审计。
        if "agent_registry" in dumped:
            restored.agent_registry = AgentRegistry.from_dict(dumped["agent_registry"])
        restored.last_handoff = dumped.get("handoff")
        return restored

    # ── L10.1 持久化第二步（只增不删）：save/load_from ＋ 原子写 ＋ 格式版本 ──
    # 为什么必须落盘（L9.1 / l91run-v4）：h(K) 在 K=1/2/3/6 全低于位置置换带 ⟹
    # 刚沉默的条目短期内不回来；而长尾是真的——K=14/15 的真实风险集有 22/6 个，
    # 位置置换下 17.5%/69.1% 的次数连一个都凑不出 ⟹ 可恢复擦除的价值在长尾 ⟹
    # 可恢复池必须撑过进程生命周期（_recoverable 是进程内 OrderedDict，进程一退
    # 就没了，L1 第一步清单 B 项即已登记）⟹ dump 的产物要能完整写进文件再读回来。

    @staticmethod
    def _format_version() -> int:
        """On-disk format version; the single source of truth for save/load_from."""
        # 新方法而非类常量：本步口径是 engine.py 只加方法。
        return 1

    def save(self, path: "str | os.PathLike[str]") -> None:
        """Atomically write the whole context (dump payload + format_version) to ``path``."""
        import json
        import os
        import tempfile

        document = {"format_version": self._format_version(), "payload": self.dump()}
        text = json.dumps(document, ensure_ascii=False, allow_nan=False) + "\n"
        target = os.fspath(path)
        # 原子写：先写同目录临时文件（同目录 ⟹ 同文件系统 ⟹ os.replace 是原子替换）。
        # 写到一半崩（write/flush/fsync 任一环抛异常）时目标文件从未被碰过、仍完整；
        # 任何异常先删临时文件再原样传播，不留污染（L10.1 验收丙）。fsync 只保证文件
        # 数据落盘；目录项的 fsync（扛掉电）在 l101run/漏列候选.md，本步不做。
        fd, staging = tempfile.mkstemp(
            prefix=f".{os.path.basename(target)}.", suffix=".tmp",
            dir=os.path.dirname(os.path.abspath(target)),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(staging, target)
        except BaseException:
            try:
                os.unlink(staging)
            except OSError:
                pass
            raise

    @classmethod
    def load_from(cls, path: "str | os.PathLike[str]") -> CtxKey:
        """Restore a CtxKey from a file written by :meth:`save`; refuse foreign versions."""
        import json
        import os

        with open(os.fspath(path), encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict) or "format_version" not in document:
            raise ValueError("not a CtxKey save file: format_version is missing")
        version = document["format_version"]
        if version != cls._format_version():
            # ⛔ 不静默降级、⛔ 不「尽力而为地读」（L10.1 验收丁）：版本不合即拒读。
            raise ValueError(
                f"format_version mismatch: file has {version!r}, engine requires "
                f"{cls._format_version()!r}; refusing to load"
            )
        if "payload" not in document:
            raise ValueError("not a CtxKey save file: payload is missing")
        return cls.load(document["payload"])

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

    # L12.2 §A 抽法一内层（园主落刀「照 l123run §A.3 抽法一落」）：_plan_select 原两段
    # （打分＋score_traces 构造、排序）的逐字提取，query 与池做成入参。等价性由构造保证：
    # 同一打分入口（score_items_with_trace）、同一排序键、零随机源（lexical.py 纯算术）
    # ⟹ 同输入逐位同输出；_plan_select 其余行零字面改（l124run/报告.md §A 逐位比对实测）。
    # pool 先 list 一次：values() 视图在打分与排序两处消费，固化快照消除重迭代边界。
    @staticmethod
    def _score_and_rank(
        query: str, pool_items: Iterable[ContextItem]
    ) -> tuple[dict[str, float], dict[str, dict[str, object]], list[ContextItem]]:
        pool = list(pool_items)
        scores, raw_traces = score_items_with_trace(query, pool)
        score_traces = {
            item_id: {"score": {"query": query, **trace}}
            for item_id, trace in raw_traces.items()
        }
        ranked = sorted(
            pool,
            key=lambda item: (-scores[item.id], -item.created_at, item.id),
        )
        return scores, score_traces, ranked

    def _write_bundle(
        self,
        bundle: ContextBundle,
        *,
        recall_self_scores: dict[str, float] | None = None,
        recall_ratios: dict[str, float] | None = None,
        recall_threshold: float | None = None,
    ) -> None:
        # L2.0：三个 recall 专用可选参数纯透传进账（默认 None ⟹ 其余操作调用方一行不改、
        # 账行为与旧版一致）。改动范围声明见 l20run/报告.md。
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
            recall_self_scores=recall_self_scores,
            recall_ratios=recall_ratios,
            recall_threshold=recall_threshold,
            rule_ref=bundle.rule_ref,  # L11.2：包上带着的身份引用透传进账（未打分的包为 None）
            score_traces=bundle.score_traces,  # L11.3：包上带着的逐 item 推导透传进账（同款：None＝未打分）
            agent_ref=self._agent,  # L14.1：select/compact/recall/scan 共用落账位—— acting_agent 盖章
        )
