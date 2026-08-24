"""Deterministic zero-network lexical scorer used by the v0.1 baseline."""

from __future__ import annotations

from collections import Counter
import copy
import math
import re
from typing import Iterable

from .models import ContextItem

_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize English words and Chinese characters, adding Chinese bigrams."""

    tokens: list[str] = []
    for segment in _TOKEN.findall(text):
        if "\u3400" <= segment[0] <= "\u9fff":
            characters = list(segment)
            tokens.extend(characters)
            tokens.extend(
                characters[index] + characters[index + 1]
                for index in range(len(characters) - 1)
            )
        else:
            tokens.append(segment.lower())
    return tokens


def score_items(query: str, items: Iterable[ContextItem]) -> dict[str, float]:
    """Return BM25-style scores for a query against a fixed candidate set."""

    candidates = list(items)
    if not candidates:
        return {}
    documents = {item.id: tokenize(item.text + " " + " ".join(item.tags)) for item in candidates}
    average_length = sum(len(tokens) for tokens in documents.values()) / len(documents) or 1.0
    document_frequency = Counter(
        token for tokens in documents.values() for token in set(tokens)
    )
    query_tokens = set(tokenize(query))
    scores: dict[str, float] = {}
    for item in candidates:
        tokens = documents[item.id]
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            count = document_frequency[token]
            inverse_frequency = math.log((len(candidates) - count + 0.5) / (count + 0.5) + 1)
            denominator = frequency + 1.5 * (0.25 + 0.75 * len(tokens) / average_length)
            score += inverse_frequency * frequency * 2.5 / denominator
        scores[item.id] = round(score, 8)
    return scores


# ── L11.2 规则身份·打分器条目（园主落刀：l111run/报告.md §① 拍一 8 条全进，一条不删）──
# 这是「账上每条带分事件的规则身份」的身份库条目之一，钥匙级一份＋事件引用（l112run 分叉#8 默认）。
# ⛔ 不是第四个「文件版本」：context_version（状态，engine.py:24,30-31）／_format_version（磁盘格式，
# engine.py:428）／__version__（包，__init__.py:7）各管一事；本身份独立于三者（#2 解耦），
# 落点在账／钥匙侧（dump 的 rule_identities），⛔ 不在 save 文件顶层。
SCORER_RULE_IDENTITY: dict[str, object] = {
    "kind": "scorer",
    "id": "bm25-lexical",
    "version": 1,  # 打分规则自己的版本；改公式／常数／分词必须 bump（与包版本无关）
    "version_scope": "scoring rules only; independent of package __version__ and disk _format_version",
    "parameters": {  # #3 参数快照：公式形状＋字面常数，与上面 score_items 的循环逐字对应（:48-57）
        "score": "sum over matched query tokens of idf * tf * 2.5 / denominator",
        # L11.5 §A①（园主定死）：对数底数写明——自然对数。来路：L11.4b 盲复算答对但那一步靠
        # 偶然（执行方从同批别的行的 trace 里 idf 精确值反推出底数）；底数不在钥匙上 ⟹ 那一步
        # 是猜中的。写明后偶然去掉。实物：score_items 与 score_items_with_trace 两处同用
        # python math.log（自然对数，底 e）。
        "idf": "ln((n_docs - df + 0.5) / (df + 0.5) + 1); ln = natural logarithm, base e (python math.log)",
        "denominator": "tf + 1.5 * (0.25 + 0.75 * doc_len / avg_len)",
        "constants": {"tf_weight": 2.5, "length_k1": 1.5, "b_min": 0.25, "b_slope": 0.75},
        "document": "tokens of (text + ' ' + ' '.join(tags))",
        "query": "set(tokenize(query))",
        # L11.5 §A②（园主定死）：补 compact 那一格。实物：compact 与 select 共用同一次打分
        # （engine.py 的 preview = self._plan_select(...)），而那次打分的池是 _plan_select 里的
        # self._active.values() ⟹ 池＝「打分那一刻的 active」——⛔ 不是 compact 之后的 active。
        # 「打分那一刻」承重：compact 的 evict 发生在打分之后，打分用的池里还包含将被擦掉的条目。
        "pool_statistics": "df / avg_len computed on the scored pool only "
                           "(select: active; compact: the active AS OF THE SCORING MOMENT — compact "
                           "reuses select's single scoring pass via preview, which runs BEFORE any "
                           "eviction, so the pool is the pre-compact active, NOT the active after "
                           "compact; recall: recoverable)",
    },
    "tokenizer": {  # #4 分词口径身份（:12-29）：分词是打分公式的一部分，换分词必须 bump
        "id": "en-lower+zh-unigram+adjacent-bigram",
        "rules": [
            "ascii runs [A-Za-z0-9_]+ lowercased",
            "cjk runs -> unigrams + adjacent bigrams",
            "bigrams never cross segment gaps",
        ],
    },
    "numerics": {  # #8 复算规约（l112run 分叉#10 默认：归身份——跟着打分规则走，不跟文件格式走）
        "float": "python float64",
        "final_rounding_decimals": 8,  # round(score, 8)（:57）——复算容差由此定
        "json_allow_nan": False,
    },
}
SCORER_RULE_REF = f'{SCORER_RULE_IDENTITY["id"]}@{SCORER_RULE_IDENTITY["version"]}'

# ── L12.2 续（l125 五格裁定①，园主 2026-08-21 落刀）：新立 bm25-lexical@2。@1 文本一字
# 不动；select／compact／recall 的事件引用仍指 @1，scan 行指 @2。@2 与 @1 的差异恰两处：
# version 1→2、pool_statistics 尾部追加 scan 格（池＝active ∪ recoverable 全池）。由构造
# 保证「@2＝@1 加 scan 格」：deepcopy 整份 @1 后仅覆写这两键。──
# L12.3 §B（园主 2026-08-21 落刀）：构造从 {**@1, ...} spread 改为 copy.deepcopy。
# 来路：spread 是浅拷贝——parameters.constants／tokenizer／tokenizer.rules／numerics
# 四处与 @1 共享引用（实测 is 全 True），故旧注释「此后 @1 的任何改动不波及 @2」在
# spread 下是假的（顶层与 parameters 两容器新建，嵌套可变值不新建）。身份库的全部
# 意义就是「冻结、可核」：deepcopy 一步保证任意深度零共享（结构是纯 JSON 形数据），
# 该句此后才为真；值逐键不变（deepcopy 不改值 ⟹ 闸二 != 比较与 @2 构造锁均不受波及，
# 实测见 l126run）。──
SCAN_SCORER_RULE_IDENTITY: dict[str, object] = copy.deepcopy(SCORER_RULE_IDENTITY)
SCAN_SCORER_RULE_IDENTITY["version"] = 2
SCAN_SCORER_RULE_IDENTITY["parameters"]["pool_statistics"] = (
    SCORER_RULE_IDENTITY["parameters"]["pool_statistics"]
    + "; scan: the full pool active + recoverable (active first, then "
      "recoverable — the whole context scored together in one flat ranking)"
)
SCAN_SCORER_RULE_REF = (
    f'{SCAN_SCORER_RULE_IDENTITY["id"]}@{SCAN_SCORER_RULE_IDENTITY["version"]}'
)


def score_items_with_trace(
    query: str, items: Iterable[ContextItem]
) -> tuple[dict[str, float], dict[str, dict[str, object]]]:
    """L11.3 甲路旁路（园主落刀：走甲路，⛔ 乙路已否决、score_items 返回形状一行不动）。

    返回 (scores, traces)：scores 直接取自 score_items（同一调用，分数路径零改动）；
    traces[item_id] 逐条带 BM25 各项（token／tf／df／idf／denominator／contribution／
    未取整和／取整终值），使接手方不读仓库代码也能复核「这个分凭什么」。
    ⚠️ 真代价（照记进注释，园主已知）：同一 BM25 公式从此两份实现入口——恒等测试
    锁得住两处漂移，⛔ 锁不住「两处都改错成一样」。
    注：terms 顺序跟随 query 集合的迭代序（与 score_items 求和同序）——保证
    round(unrounded_sum, 8) 与 score_items 的终值逐位相等；排序版会在第 8 位小数
    端引入理论漂移（浮点加法不结合），故不排。
    """
    scores = score_items(query, items)  # 权威分数来自原入口；新入口只旁出推导
    candidates = list(items)
    if not candidates:
        return {}, {}
    documents = {item.id: tokenize(item.text + " " + " ".join(item.tags)) for item in candidates}
    average_length = sum(len(tokens) for tokens in documents.values()) / len(documents) or 1.0
    document_frequency = Counter(
        token for tokens in documents.values() for token in set(tokens)
    )
    query_tokens = set(tokenize(query))
    traces: dict[str, dict[str, object]] = {}
    for item in candidates:
        tokens = documents[item.id]
        frequencies = Counter(tokens)
        terms: list[dict[str, object]] = []
        score = 0.0
        for token in query_tokens:  # 与 score_items 同一集合、同一迭代序 ⟹ 同一累加序
            frequency = frequencies[token]
            if not frequency:
                continue
            count = document_frequency[token]
            inverse_frequency = math.log((len(candidates) - count + 0.5) / (count + 0.5) + 1)
            denominator = frequency + 1.5 * (0.25 + 0.75 * len(tokens) / average_length)
            contribution = inverse_frequency * frequency * 2.5 / denominator
            terms.append({
                "token": token,
                "tf": frequency,
                "df": count,
                "idf": inverse_frequency,
                "denominator": denominator,
                "contribution": contribution,
            })
            score += contribution
        traces[item.id] = {
            "n_docs": len(candidates),
            "avg_len": average_length,
            "doc_len": len(tokens),
            "terms": terms,
            "unrounded_sum": score,
            "rounded": round(score, 8),
        }
    return scores, traces
