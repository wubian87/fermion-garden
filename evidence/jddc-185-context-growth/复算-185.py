#!/usr/bin/env python3
"""185 对照臂（compaction 默认策略）上下文增长的复算脚本 —— 零调用、只数数。

它做一件事：把一次已完成跑的 dsh session 账读出来，逐 turn 抽 usage 的四个数，
写成不含任何对话内容的 token-trajectory.csv 与 summary.json。

⛔ 输入是受限数据：这次跑的料来自 JDDC（京东客服对话数据集），受其许可约束，
   **不随本仓发布**；session 账里含逐字对话，也不发布。本目录只发布本脚本的**输出**
   （纯计数）＋ 输入文件的 sha256，让第三方能核「数是从哪来的、有没有被改过」。

用法：
    python3 复算-185.py <session.jsonl.zstd 的路径>
需要本机有 zstd。输出写到本脚本所在目录。
"""
import json, subprocess, sys, hashlib, csv
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(__doc__)
src = Path(sys.argv[1]).expanduser()
出 = Path(__file__).resolve().parent

sha = hashlib.sha256(src.read_bytes()).hexdigest()
raw = subprocess.run(["zstd", "-dc", str(src)], capture_output=True, text=True).stdout
evs = [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

喂 = [e for e in evs if e.get("type") == "user/message" and e.get("surfaceOp") == "append"
      and e["data"].get("source", {}).get("标记") == "jddc-185"]
回 = [e for e in evs if e.get("type") == "assistant/message" and e.get("surfaceOp") == "append"]
压 = [e for e in evs if str(e.get("type", "")).startswith("compaction/")]

行 = []
for i, e in enumerate(回, 1):
    u = e["data"].get("usage") or {}
    inn = u.get("inputTokens") or 0
    cr = u.get("cacheReadTokens") or 0
    行.append({"turn": i, "inputTokens": inn, "cacheReadTokens": cr,
               "请求量_in加cacheRead": inn + cr,
               "outputTokens": u.get("outputTokens") or 0,
               "reasoningTokens": u.get("reasoningTokens") or 0})

with (出 / "token-trajectory.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(行[0].keys())); w.writeheader(); w.writerows(行)

单调 = all(a["cacheReadTokens"] <= b["cacheReadTokens"] for a, b in zip(行, 行[1:]))
摘 = {
    "源session_sha256": sha,
    "源session_文件名": src.name,
    "事件数": len(evs),
    "喂入客户消息数": len(喂),
    "assistant_turn数": len(回),
    "compaction事件数": len(压),
    "首turn": {k: 行[0][k] for k in ("inputTokens", "cacheReadTokens", "请求量_in加cacheRead")},
    "末turn": {k: 行[-1][k] for k in ("inputTokens", "cacheReadTokens", "请求量_in加cacheRead")},
    "cacheRead末态": 行[-1]["cacheReadTokens"],
    "cacheRead是否单调不降": 单调,
    "inputTokens最大": max(r["inputTokens"] for r in 行),
    "总请求量_in加cacheRead": sum(r["请求量_in加cacheRead"] for r in 行),
    "口径": "inputTokens 只记缓存未命中部分；单 turn 真实请求量＝inputTokens+cacheReadTokens。"
            "只看 inputTokens 会把这一臂读小两个数量级以上。",
}
(出 / "summary.json").write_text(json.dumps(摘, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(摘, ensure_ascii=False, indent=1))
