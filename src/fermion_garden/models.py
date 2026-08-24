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
    # L12 收账后补（2026-08-21，园主落刀「落」）：scan 从 L12.2 §B 起就在落账
    # （engine.py 的 scan 构造点），而这一行仍写三值 ⟹ 一个接手方读得到的地方写着
    # 过时的东西（同族先例＝L11.5「分隔符只在代码里、不在钥匙上」）。
    # 加枚举值零行为变化：Literal 运行时不校验，闸在 LedgerEvent.__post_init__。
    # 值域是四值不是五值：record 经 engine.py 的 ledger.append 直落账，不经 ContextBundle
    # （八个构造点核过：select×4／compact×2／recall×1／scan×1）。
    operation: Literal["select", "compact", "recall", "scan"]
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
    # L11.2 新增（纯增量，默认 None，现有构造调用一行不改）：本包打分所用规则的身份引用。
    # None ＝ 本包未经打分（空池／超预算占位决策）；打过分的包由 _plan_select／recall 落身份。
    rule_ref: str | None = None
    # L11.3 新增（纯增量）：score_items_with_trace 逐 item 的推导，包打分时算一份、
    # compact 沿用 preview（l112run 分叉#6 默认，与 score_by_id 同款）。
    # 结构：{item_id: {"score": {"query": 打分原文, **推导}, "self": {...仅 recall 行}}};
    # query 嵌原文而非引用 criterion——recall 的 criterion 是 trigger.strip()（engine.py recall
    # 处），与打分原文（trigger 未 strip）不是同一个串，嵌原文消歧。
    score_traces: dict[str, dict[str, object]] | None = None

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
            "rule_ref": self.rule_ref,
            "score_traces": self.score_traces,
        }

