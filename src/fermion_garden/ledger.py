"""Append-only in-memory audit ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable

# ── L12.2 §C operation 闸值域（园主落刀）：LedgerEvent.operation 的合法值全集 ──
# 基准是「账面实际值域」而非 models.py 的 Literal：第四个旧值 record 由 CtxKey.record
# 直接 ledger.append 落账（engine.py record 路径），不经 ContextBundle ⟹ models.py:44 的
# Literal 三值（select/compact/recall）漏 record——照它写 ⟹ 恢复任何含 record 行的旧账
# 在读写两侧闸下逐行 ValueError。scan 是 L12.2 §B 新动作的落账值（§2.5 园主落刀）。
# protect 是 L17 pin_latest 的落账值（工程态保护；纯增量：旧五个值一行未动）。
LEDGER_OPERATIONS: frozenset[str] = frozenset(
    {"record", "select", "compact", "recall", "scan", "protect"}
)


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
    # L2.0 新增（纯增量：上面 16 个字段的名字与含义一行未动）——recall 决策的 D3 归一化三件套。
    # 只在 operation=="recall" 的行上打戳（含分子可见的 score 字段），其余操作恒 None。
    recall_self_score: float | None = None
    recall_ratio: float | None = None
    recall_threshold: float | None = None
    # L11.2 新增（纯增量，同 L2.0 口径：上面 19 个字段的名字与含义一行未动）——
    # 规则身份的事件引用。None ＝ 本行未经打分（record 行 engine.py:59 的 0.0 是占位、
    # 空池／超预算两条 conflict 路径的 0.0 同为占位）；打过分的行引用身份库
    # （库本体在钥匙级一份，见 CtxKey._rule_identities；select/compact 引用打分器，
    # recall 引用打分器＋门槛层——l111run/报告.md §① #1/#7）。
    rule_ref: str | None = None
    # L11.3 新增（纯增量）：本行分数的逐 token 推导（score_items_with_trace 旁路，甲路）。
    # None ＝ 本行未经打分（record／占位 conflict）；select/compact 行形如
    # {"score": {...}}；recall 行形如 {"score": {...}, "self": {...}}，self 的 query
    # 嵌该条目自身文本（recall 自分处是 per-item 全池打分，每条必须带 query 身份，
    # 否则 |pool| 条 self-trace 分不清出自哪次打分——l111run/报告.md §②甲-2）。
    score_trace: dict[str, object] | None = None
    # L14.1 新增（纯增量，默认 None，现有构造调用一行不改）：存在身份的事件引用——
    # 这一步是哪个存在干的。None ＝ 未归因（L14.1 之前的旧账、或未设 acting_agent
    # 的引擎）。号由 AgentRegistry 唯一发放（9 位定宽，agents.py）；与 rule_ref 分层：
    # rule_ref 归因「用哪条判据」，agent_ref 归因「哪个存在」。
    agent_ref: str | None = None

    # L12.2 §C（园主落刀）：operation 闸。落点选 LedgerEvent.__post_init__ 是推导不是选择——
    # 它是读写两侧都必经的唯一构造点（写经 DecisionLedger.append、读经 CtxKey.load 的
    # event_from_dict），一处放闸双侧生效（外部手写 JSON 的 load/load_from 也在读侧过闸）。
    # 口径沿用 L10.1「⛔ 不静默降级、⛔ 不尽力而为地读」：值域外一律 ValueError 拒。
    # operation=None 一并拒：现状是 None 经 save→load_from 被 engine 的 event_from_dict
    # 读成字符串 "None"（str() 静默变形），闸落在构造点 ⟹ 变形值照样拦下。
    def __post_init__(self) -> None:
        if self.operation not in LEDGER_OPERATIONS:
            raise ValueError(
                f"unknown ledger operation {self.operation!r}; refusing to construct "
                f"(known operations: {sorted(LEDGER_OPERATIONS)})"
            )

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
            "recall_self_score": self.recall_self_score,
            "recall_ratio": self.recall_ratio,
            "recall_threshold": self.recall_threshold,
            "rule_ref": self.rule_ref,
            "score_trace": self.score_trace,
            "agent_ref": self.agent_ref,
        }


class DecisionLedger:
    # L2.0 · D3 召回门槛（唯一源）：ratio(i) = score_T(i) / self(i) ≥ 此值才召回。
    # 取值 ＝ l18run/判据结果.json 的 D3 全局①窗口 (0.288950, 0.294872] 中点——唯一同时满足
    # 所有档的取法（规则写死，非挑选）。
    # 「在单一场景（9 条料 × 5 道题，同一次设计写的）上标定；全局①窗口相对宽度仅 0.0203，
    #   存在但薄；⛔ 未跨料验证。」
    RECALL_RATIO_THRESHOLD = 0.2919106045201252

    # ── L11.2 规则身份·recall 门槛层（园主落刀：l111run/报告.md §① #5/#6/#7 全进）──
    # 上面 61-66 行注释里门槛自带的限度，从此不只活在注释：以可机读结构随钥匙走
    # （dump 的 rule_identities）。乙档要挡的正是「记下来的数看起来比它本身硬」——
    # 钥匙上只有 0.2919… 这个数时，接手方读不出它薄；limits 让「薄」在钥匙上可读。
    # recall 行的事件引用是「打分器＋门槛层」两层（#7）：打分器身份盖不住比值与门槛，
    # 而限度声明恰恰挂在这一层。
    RECALL_GATE_IDENTITY: dict[str, object] = {
        "kind": "recall_gate",
        "id": "d3-self-ratio",
        "version": 1,  # 门槛规则自己的版本；改定义／门槛必须 bump（与包版本／磁盘格式解耦）
        "version_scope": "recall gate only; independent of package __version__ and disk _format_version",
        "definition": "ratio(i) = score_T(i) / self(i); recall iff ratio >= threshold; "
                      "rank by score desc, created_at desc, id asc; cut at budget",
        "self_definition": "self(i) = score_items(item_i.text, same recoverable pool)[i] "
                           "(per-item full-pool scoring)",
        "self_zero_policy": "self(i) == 0 -> ratio defined as 0.0 -> not recalled (engine.py:299-301)",
        "threshold": RECALL_RATIO_THRESHOLD,
        "calibration": {  # #5 门槛标定来路（快照语义：将来重新标定，不改旧账上的这一段）
            "source": "l18run/判据结果.json · D3 全局①窗口 (0.288950, 0.294872] 取中点（规则写死，非挑选）",
            "scenario": "单一场景：9 条料 × 5 道题，同一次设计写的",
        },
        "limits": [  # #6 限度自声明（结构化，⛔ 不许自由文本——l112run 分叉#6 默认）
            {"kind": "calibration_scope", "detail": "单一场景标定：9 条料 × 5 道题，同一次设计写的"},
            {"kind": "window_relative_width", "value": 0.0203, "detail": "全局①窗口相对宽度仅 0.0203——存在但薄"},
            {"kind": "cross_material_validation", "status": "unverified", "detail": "⛔ 未跨料验证"},
        ],
    }
    RECALL_GATE_RULE_REF = f'{RECALL_GATE_IDENTITY["id"]}@{RECALL_GATE_IDENTITY["version"]}'

    # ── L11.5 §A③ 规则身份·账字段读法（园主定死：新立 ledger-fields@1，⛔ 不塞进 bm25-lexical@1
    # ——它跟打分规则无关，塞进去会污染 scorer 的语义）。专管「账上的字段怎么读」。
    # 首格：item_content_sha256 的序列化口径——算法在下方 append() 的 item_content_sha256
    # 赋值处（text 与各 tag 用分隔符拼接再取 sha256），那个分隔符原先只在代码里、不在钥匙上
    # ⟹ 接手方验不了。完整口径（拼接顺序＋分隔符确切字符）由此写上钥匙。纯增量：
    # rule_identities 本来就是 dict，加一条不动任何现有键。──
    LEDGER_FIELDS_IDENTITY: dict[str, object] = {
        "kind": "ledger_fields",
        "id": "ledger-fields",
        "version": 1,
        "version_scope": "how to read ledger fields; independent of scoring rules and disk format",
        "fields": {
            "item_content_sha256": {
                "algorithm": "sha256 hexdigest of the utf-8 bytes of the serialization below",
                "serialization": "item.text + SEP + SEP.join(item.tags), in that order",
                "separator": "SEP = U+001F UNIT SEPARATOR (single byte 0x1f)",
                "note": "SEP is appended after text even when tags is empty "
                        "(the tail then is text + SEP + empty string)",
            },
        },
    }
    LEDGER_FIELDS_RULE_REF = f'{LEDGER_FIELDS_IDENTITY["id"]}@{LEDGER_FIELDS_IDENTITY["version"]}'
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
        recall_self_scores: dict[str, float] | None = None,
        recall_ratios: dict[str, float] | None = None,
        recall_threshold: float | None = None,
        rule_ref: str | None = None,
        score_traces: dict[str, dict[str, object]] | None = None,
        agent_ref: str | None = None,
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
                    recall_self_score=(recall_self_scores or {}).get(decision.item_id),
                    recall_ratio=(recall_ratios or {}).get(decision.item_id),
                    recall_threshold=recall_threshold,
                    rule_ref=rule_ref,
                    score_trace=(score_traces or {}).get(decision.item_id),
                    agent_ref=agent_ref,
                )
            )

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
            for event in self._events
        )
