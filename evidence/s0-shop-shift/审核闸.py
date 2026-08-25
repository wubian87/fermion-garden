#!/usr/bin/env python3
"""S0 ④ 臂的审核闸：把审核员那条回复读成一个「放行／退回」的决定。

⚠️ **fail closed**：只有「解析出 dict，且『放行』字段确实是布尔 True」这一条路才放行。
   解析失败／字段缺失／字段不是布尔（含字符串 "false"、"0"、"否"）一律**退回并标人工复核**。

理由一句：审核员这个角色的职责是「查账不放行问题件」⟹ **它读不出结果的时候，默认必须是拦，不是放。**

⟵ 这段逻辑 2026-08-26 从 `八爪鱼-S0.py` 里析出到本文件（补丁 A 的一部分），
   为的是让这道闸能被 `tests/test_s0_audit_gate.py` 直接验，而不是只能读代码相信它。
   ⛔ 补丁前的原始代码（fail **open**）逐字列在 `八爪鱼-S0.py` 头注里；
   ⚠️ 补丁晚于 2026-08-25 那次真跑，且**未影响那次读数** ——
   账上 52 个点是 放行 51 ／ 退回 1 ／ **解析失败 0**，fail open 那条分支一次没走过。
"""
import json
import re


def 抽JSON(文: str) -> dict | None:
    """从模型回复里抠出第一个平层 JSON 对象；抠不出或解析不了返回 None。"""
    文 = re.sub(r"```(?:json)?", "", 文 or "").strip()
    m = re.search(r"\{[^{}]*\}", 文, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def 判审核(审核回复: str) -> tuple[bool, list[str], str, bool]:
    """读审核员的回复，返回 (放行, 问题, 审核态, 需人工复核)。

    fail closed：拿不准一律不放行。
    """
    审o = 抽JSON(审核回复)
    if not isinstance(审o, dict):
        return (False,
                ["审核回复无法解析为 JSON —— fail closed，按退回处理，需人工复核"],
                "解析失败·按退回落账", True)
    if not isinstance(审o.get("放行"), bool):
        return (False,
                [f"审核回复的「放行」字段不是布尔值（收到 {审o.get('放行')!r}）"
                 " —— fail closed，按退回处理，需人工复核"],
                "放行字段非布尔·按退回落账", True)
    放行 = 审o["放行"]
    return (放行, list(审o.get("问题") or []), "放行" if 放行 else "退回", False)
