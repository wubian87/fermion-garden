"""S0 ④ 臂审核闸的 fail-closed 单测（零模型调用、零网络）。

验的是 `evidence/s0-shop-shift/审核闸.py` 里那道闸：**审核员的回复读不干净时，倒向哪边。**

这道闸 2026-08-26 之前是 **fail open** —— 解析失败直接放行，`bool("false")` 也判成真。
那跟审核员自己那句职责（「查账不放行问题件」）是反的。补丁后必须 **fail closed**。

⚠️ 本文件只验补丁后的行为，**不主张**补丁改变了 2026-08-25 那次跑的读数
   ——那次账上 52 点是 放行 51 ／ 退回 1 ／ 解析失败 0，fail open 那条分支一次没走过，
   逐条见 `evidence/s0-shop-shift/八爪鱼-S0.py` 头注。
"""
import importlib.util
import sys
import unittest
from pathlib import Path

_闸路径 = Path(__file__).resolve().parents[1] / "evidence" / "s0-shop-shift" / "审核闸.py"
_spec = importlib.util.spec_from_file_location("s0_审核闸", _闸路径)
审核闸 = importlib.util.module_from_spec(_spec)
sys.modules["s0_审核闸"] = 审核闸
_spec.loader.exec_module(审核闸)


class S0审核闸FailClosed(unittest.TestCase):
    # ── 该放行的照放 ─────────────────────────────────────────
    def test_布尔true放行(self):
        放行, 问题, 态, 需人工 = 审核闸.判审核('{"放行": true, "问题": []}')
        self.assertTrue(放行)
        self.assertEqual(态, "放行")
        self.assertFalse(需人工)

    def test_带代码围栏也读得出(self):
        放行, _, 态, _ = 审核闸.判审核('```json\n{"放行": true, "问题": []}\n```')
        self.assertTrue(放行)
        self.assertEqual(态, "放行")

    # ── 该退回的照退 ─────────────────────────────────────────
    def test_布尔false退回并带上问题(self):
        放行, 问题, 态, 需人工 = 审核闸.判审核('{"放行": false, "问题": ["答非所问"]}')
        self.assertFalse(放行)
        self.assertEqual(态, "退回")
        self.assertEqual(问题, ["答非所问"])
        self.assertFalse(需人工)   # 正常退回，不是闸兜住的

    # ── fail closed：三种「读不干净」全部倒向退回 ─────────────
    def test_解析失败不许放行(self):
        """补丁前：这一条直接放行。"""
        放行, 问题, 态, 需人工 = 审核闸.判审核("审核意见：这稿没问题，可以发")
        self.assertFalse(放行, "解析失败必须 fail closed")
        self.assertEqual(态, "解析失败·按退回落账")
        self.assertTrue(需人工)
        self.assertTrue(问题, "兜住的时候必须留下一句为什么")

    def test_放行字段是字符串不许放行(self):
        """补丁前：bool("false") 是 True ⟹ 放行。这是与解析失败并列的第二个洞。"""
        for 假值 in ('"false"', '"0"', '"否"', '"true"', '0', '1', 'null', '[]'):
            with self.subTest(放行值=假值):
                放行, 问题, 态, 需人工 = 审核闸.判审核(f'{{"放行": {假值}, "问题": []}}')
                self.assertFalse(放行, f"放行={假值} 不是布尔，必须 fail closed")
                self.assertEqual(态, "放行字段非布尔·按退回落账")
                self.assertTrue(需人工)

    def test_缺放行字段不许放行(self):
        """补丁前：.get("放行", True) 的默认值是 True ⟹ 放行。"""
        放行, _, 态, 需人工 = 审核闸.判审核('{"问题": []}')
        self.assertFalse(放行, "缺字段必须 fail closed")
        self.assertEqual(态, "放行字段非布尔·按退回落账")
        self.assertTrue(需人工)

    def test_空回复不许放行(self):
        for 回 in ("", "   ", None):
            with self.subTest(回复=回):
                放行, _, _, 需人工 = 审核闸.判审核(回)
                self.assertFalse(放行)
                self.assertTrue(需人工)

    # ── 元：闸的返回形状本身也钉住 ────────────────────────────
    def test_问题永远是list(self):
        for 回 in ('{"放行": true}', '{"放行": false}', "读不出", '{"放行": "x"}'):
            with self.subTest(回复=回):
                self.assertIsInstance(审核闸.判审核(回)[1], list)


if __name__ == "__main__":
    unittest.main()
