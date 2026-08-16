#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 120 注验证器：机判修虫子 v2 提交（全脚本，无 LLM judge；判卷逻辑与 119 同款，题面欠定化在题侧不在判卷侧）。

公开边界：本文件只用于受控实验，不是安全沙箱，不要用它执行任意第三方代码。
默认拒绝执行；显式确认后仍要求 Linux ``unshare -n``，不可用时失败关闭，不降级。

用法：python3 controlled_validator.py --i-understand-this-executes-code 候选.py 当前最好.json
当前最好.json ＝ {"过题数": int, "代码": str}（接手时的最好版程序全文）。
stdout 恰一行 JSON：{合法, 过题数, 推进, 错误, 异常, 耗时, 断网方式, 改动行数, 明细}

判卷规则（事前冻结，见 配方.md 第三节；判卷口径＝考题-公开.json（28 全带期望值）＋考题-私持.json，公开面文件不进判卷）：
- 改动行数 ＝ 候选 vs 接手最好版的 unified diff 增删行合计；>20 ⟹ 非法（超行数上限）。
- AST 白名单：只许 math, random, itertools, functools, collections, heapq, array, copy, json, sys, time,
  dataclasses, typing；禁 datetime/calendar；禁 open/eval/exec/compile/__import__ 调用。
- 判卷：公开 28＋私持 18＝46 题各跑一次，期望值逐题 JSON 全等；过题数＝通过数。
- 确定性：整套判卷跑两遍，任一逐题通过映射不同 ⟹ 非法（非确定）。
- 推进 ＝ 过题数 > 接手时过题数。合法 ＝ 行数／白名单／两遍判卷全过且模块可导入可运行。
- 异常记账照 118 修复版：各 except 落异常类型与消息进「异常」字段（进账不进判定）。
限时：环境变量 值表_TIMEOUT（秒，默认 60，整套判卷每遍的墙钟上限）。
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

目录 = Path(__file__).resolve().parent
题目录 = 目录
行数上限 = 20
白名单 = {
    "math", "random", "itertools", "functools", "collections", "heapq", "array",
    "copy", "json", "sys", "time", "dataclasses", "typing",
}
禁调用 = {"open", "eval", "exec", "compile", "__import__", "input"}


def 改动行数(旧: str, 新: str) -> int:
    差 = list(difflib.unified_diff(旧.splitlines(), 新.splitlines(), lineterm=""))
    return sum(1 for 行 in 差 if 行.startswith(("+", "-")) and not 行.startswith(("+++", "---")))


def 查源(代码: str) -> str | None:
    """AST 白名单检查；返回违规描述或 None。"""
    import ast
    try:
        树 = ast.parse(代码)
    except SyntaxError as exc:
        return f"语法错误: {type(exc).__name__}: {exc}"
    for 节点 in ast.walk(树):
        if isinstance(节点, ast.Import):
            for 名 in 节点.names:
                根 = 名.name.split(".")[0]
                if 根 not in 白名单:
                    return f"违规导入: {名.name}"
        elif isinstance(节点, ast.ImportFrom):
            根 = (节点.module or "").split(".")[0]
            if 根 and 根 not in 白名单:
                return f"违规导入: from {节点.module}"
        elif isinstance(节点, ast.Call) and isinstance(节点.func, ast.Name) and 节点.func.id in 禁调用:
            return f"违规调用: {节点.func.id}"
    return None


_判卷工人 = r'''# -*- coding: utf-8 -*-
import contextlib, importlib.util, io, json, signal, socket, sys

def 拒绝(*a, **k):
    raise PermissionError("网络已禁用")
socket.socket = 拒绝
socket.create_connection = 拒绝
socket.socketpair = 拒绝
socket.getaddrinfo = 拒绝

候选路, 公开路, 私持路 = sys.argv[1], sys.argv[2], sys.argv[3]

def 标准化(v):
    if isinstance(v, tuple):
        return [标准化(x) for x in v]
    if isinstance(v, list):
        return [标准化(x) for x in v]
    if isinstance(v, dict):
        return {k: 标准化(x) for k, x in v.items()}
    return v

def 规范(v):
    return json.dumps(标准化(v), sort_keys=True, ensure_ascii=False)

class 超时(Exception):
    pass

def 响铃(信号, 帧):
    raise 超时()

signal.signal(signal.SIGALRM, 响铃)

def 载模块(路径):
    规格 = importlib.util.spec_from_file_location("受验程序", 路径)
    模块 = importlib.util.module_from_spec(规格)
    signal.alarm(10)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            规格.loader.exec_module(模块)
    finally:
        signal.alarm(0)
    return 模块

def 跑一条(模块, 条):
    期望 = 条["期望"]
    try:
        函数 = getattr(模块, 条["调"][0])
        # 取表也在被测路径内（v2.2 约定：解析对无效日期抛 ValueError——期望可为该异常），一并入 try
        表 = 模块.解析(条["表"]) if 条.get("表") else None
        实参 = [表 if a == "@表" else a for a in 条["调"][1:]]
        if isinstance(期望, dict) and "抛" in 期望:
            函数(*实参)
            return False, "期望抛异常但正常返回"
        return 规范(函数(*实参)) == 规范(期望), None
    except Exception as exc:
        if isinstance(期望, dict) and "抛" in 期望:
            return type(exc).__name__ == 期望["抛"], None
        return False, f"{type(exc).__name__}: {exc}"

def main():
    条们 = json.loads(open(公开路, encoding="utf-8").read()) + json.loads(open(私持路, encoding="utf-8").read())
    模块 = 载模块(候选路)
    过 = {"公开": 0, "私持": 0}
    每题 = {}
    逐题异常 = {}
    for 条 in 条们:
        signal.alarm(3)
        try:
            好, 异常 = 跑一条(模块, 条)
        except 超时:
            好, 异常 = False, "超时"
        except Exception as exc:
            好, 异常 = False, f"{type(exc).__name__}: {exc}"
        finally:
            signal.alarm(0)
        每题[条["名"]] = 好
        if 异常:
            逐题异常[条["名"]] = 异常
        # 名字带「私持」标记的按私持计数？不——按文件来源计。见下。
    sys.stdout.write(json.dumps({"每题": 每题, "逐题异常": 逐题异常}, ensure_ascii=False))

# 按来源分开计数：先公开后私持，条数各自已知
if __name__ == "__main__":
    main()
'''


def 判卷一遍(候选: Path, 工目录: Path, 限时: int, 断网: bool) -> tuple[dict | None, str | None]:
    工人 = 工目录 / "判卷工人.py"
    工人.write_text(_判卷工人, encoding="utf-8")
    命令 = [sys.executable, "-I", str(工人), str(候选), str(题目录 / "tests-public.json"), str(题目录 / "tests-held-out.json")]
    if 断网:
        unshare = shutil.which("unshare")
        if not unshare:
            return None, "缺少 unshare，拒绝降级执行候选代码"
        命令 = [unshare, "-n", "--", *命令]
    try:
        完成 = subprocess.run(命令, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=限时, check=False)
    except subprocess.TimeoutExpired:
        return None, "判卷超时"
    except Exception as exc:  # noqa: BLE001 —— 异常记账
        return None, f"{type(exc).__name__}: {exc}"
    if 完成.returncode != 0:
        尾 = (完成.stderr or "").strip().splitlines()[-1] if 完成.stderr else ""
        return None, f"判卷工人退出码 {完成.returncode}: {尾[:300]}"
    try:
        return json.loads(完成.stdout), None
    except Exception as exc:  # noqa: BLE001
        return None, f"判卷输出解析失败 {type(exc).__name__}: {完成.stdout[:200]!r}"


def main() -> int:
    开始 = time.monotonic()
    限时 = int(os.environ.get("值表_TIMEOUT", "60"))
    确认旗 = "--i-understand-this-executes-code"
    if len(sys.argv) != 4 or sys.argv[1] != 确认旗:
        print(json.dumps({
            "合法": False,
            "过题数": 0,
            "推进": False,
            "错误": "默认拒绝执行候选代码",
            "异常": f"需要显式参数 {确认旗}，并应在隔离容器内运行",
            "耗时": round(time.monotonic() - 开始, 6),
            "断网方式": "unshare-required",
            "改动行数": None,
            "明细": None,
        }, ensure_ascii=False, separators=(",", ":")))
        return 2
    候选路 = Path(sys.argv[2])
    最好路 = Path(sys.argv[3])
    出 = {"合法": False, "过题数": 0, "推进": False, "错误": None, "异常": None,
          "断网方式": "unshare-required", "改动行数": None, "明细": None}
    try:
        if not shutil.which("unshare"):
            raise RuntimeError("缺少 unshare，拒绝降级执行候选代码")
        最好 = json.loads(最好路.read_text(encoding="utf-8"))
        代码 = 候选路.read_text(encoding="utf-8")
        出["改动行数"] = 改动行数(最好["代码"], 代码)
        知识检 = os.environ.get("值表_知识检") == "1"  # P7 裸模型探针用：diff 行数照记，超限不毙（落点表 §3 P7 行）
        if 出["改动行数"] > 行数上限 and not 知识检:
            出["错误"] = "超行数上限"
            出["异常"] = None
        else:
            违 = 查源(代码)
            if 违:
                出["错误"] = "语法错误" if 违.startswith("语法错误") else "违规源码"
                出["异常"] = 违
            else:
                断网 = True
                with tempfile.TemporaryDirectory(prefix="exam119-") as 临时:
                    两遍 = []
                    for _ in range(2):
                        结果, 错 = 判卷一遍(候选路, Path(临时), 限时, 断网)
                        if 错:
                            出["错误"], 出["异常"] = ("运行错", 错) if ("退出码" in 错 or "超时" in 错) else ("判卷失败", 错)
                            break
                        两遍.append(结果)
                    else:
                        过1 = sum(两遍[0]["每题"].values())
                        过2 = sum(两遍[1]["每题"].values())
                        if 两遍[0]["每题"] != 两遍[1]["每题"]:
                            变化题 = sorted(
                                名 for 名 in 两遍[0]["每题"]
                                if 两遍[0]["每题"][名] != 两遍[1]["每题"][名]
                            )
                            出["错误"], 出["异常"] = "非确定", {
                                "两遍过题数": [过1, 过2],
                                "逐题结果变化": 变化题,
                            }
                            出["两遍"] = [过1, 过2]
                        else:
                            名集公开 = {条["名"] for 条 in json.loads((题目录 / "tests-public.json").read_text(encoding="utf-8"))}
                            公开过 = sum(v for k, v in 两遍[0]["每题"].items() if k in 名集公开)
                            私持过 = 过1 - 公开过
                            异常账 = {
                                "第一遍": 两遍[0].get("逐题异常", {}),
                                "第二遍": 两遍[1].get("逐题异常", {}),
                            }
                            出.update({"合法": True, "过题数": 过1, "明细": {
                                "公开": 公开过,
                                "私持": 私持过,
                                "题数": len(两遍[0]["每题"]),
                                "逐题异常": 异常账,
                            }})
                            出["推进"] = 过1 > int(最好["过题数"])
    except Exception as exc:  # noqa: BLE001 —— 异常记账：类型与消息进账
        出["错误"] = 出["错误"] or "验证链失败"
        出["异常"] = f"{type(exc).__name__}: {exc}"
    出["耗时"] = round(time.monotonic() - 开始, 6)
    print(json.dumps(出, ensure_ascii=False, separators=(",", ":")))
    # 判卷链失败（运行错/判卷失败/验证链失败）以非零退出码结束，供流水线按退出码判定；
    # 规则性拒绝（超行数上限/违规源码/非确定）是正常判卷结果，退出码仍为 0。
    return 1 if 出["错误"] in {"运行错", "判卷失败", "验证链失败"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
