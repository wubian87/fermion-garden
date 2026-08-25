# 费米子乐园 / Fermion Garden

> Research preview: an auditable, reversible context selector for multi-agent handoffs.

**GOAI Agent Infra 初赛仓库。** 参赛名「**费米子乐园·八爪鱼**」：费米子乐园＝共享上下文环境与 `ctx-key` Skill；八爪鱼＝住在其中、完成软件修复任务的三职能 Agent 团队（诊断／修复／验证，设计阶段，AgentTeams 接入未完成）。

参赛主体：重庆伴月之星网络科技有限公司 · [byzx.xyz](https://byzx.xyz)。评委请以本仓库、方案文档和 500 字简介为准；官网是公司主页，不是本赛的运行证据。

评委或 AI 请先读：`README.md` → `STATUS.md` → `EVIDENCE.md` → `examples/offline_demo.py`。不要把本仓库读成已完成的多 Agent 产品。

多 Agent 共用的上下文会持续增长。费米子乐园把“下一位 Agent 这一步该读什么”做成四个显式操作：`select` 选择、`compact` 可逆移出、`recall` 按新证据召回、`scan` 全池排名（只读，零状态改动）。每次决定都留下理由、版本与 `trace_id`。

**账不是「记了一行」，是可以逐 token 复算的。**每条打过分的账行带 `rule_ref`（用的哪条判据，如 `bm25-lexical@2`）与 `score_trace`——里面是这次打分的 query、`n_docs`、`avg_len`、`doc_len`，以及逐个 token 的 `tf / df / idf / denominator / contribution`，最后是 `unrounded_sum` 与 `rounded`。**第三方拿账行就能把分自己算一遍，不用相信引擎。**

L14.1 还加入了单进程的 `AgentRegistry`：给参与者发 9 位号，让账行带 `agent_ref`，并在 `dump(to_agent=...)` 中记录一次 handoff 的两端。它是可审计的身份归因，不是权限系统、消息总线或 Agent 调度器；接手方 `load` 后必须自己设置 `acting_agent`，旧钥匙不会替它冒充身份。

## 当前状态

这是从私人实验母库白名单提取的初赛代码候选，不是完成品。

- **已实现**：
  - 零网络词面基线，`select / compact / recall / scan` 四个显式操作；
  - `pin_latest` 工程态保护（版本化材料的最新态钉在活动区，`protect` 账行）；
  - 可恢复账本：移出项进可恢复区，不做永久删除；
  - **可复算的归因**：账行带 `rule_ref`（判据身份，含版本）与 `score_trace`（逐 token 的 tf/df/idf/贡献），第三方可独立重算每一个分；
  - **落盘与回读**：`save` 原子写整份上下文（同目录临时文件 ＋ `os.replace`），`load_from` 带 `format_version` 闸——**版本不匹配一律拒读，⛔ 不静默降级**；
  - 单进程参与者身份（9 位号）、账行 `agent_ref` 归因与 `dump/load` 两端 handoff 审计；
  - 两个离线演示、单元测试（68 个）；
  - 第 118–123 轮机械证据快照，L15/L16 真实任务对照与 L17/L18 重放等价，S0 店铺客服班三臂同流。
- **尚未实现**：AgentTeams 适配器、消息总线、分布式 Trace、真实的 `investigator / fixer / verifier` 三 Agent 运行闭环、嵌入 provider、生产沙箱。
  ⚠️ 一处必须说准：[`evidence/s0-shop-shift/`](evidence/s0-shop-shift/) 里确有一次**三角色**（分诊／办理／审核）的真实调用运行，
  但它跑在一次性实验脚本里，**⛔ 不是本仓引擎的产品接口，⛔ 也不是 AgentTeams 闭环**。
  那次运行验的是**受控客服班上三角色之间的上下文交接结构**，⛔ 不是「AI 自动运营店铺」——
  定价、库存、履约、支付一概不碰。
- **尚未证明**：上下文选择能提升任务成功率。第 120 轮正式结果是三种读法打平，选择臂的重复踩坑反而更多。第 121 轮在同一题上分出：死路记录写成禁令比写成中性描述重踩更少（R 0.55 对 0.65；Z 双 0.90 打平）——量的是记录写法的效应，不是任务成功率。第 122 轮三臂（判线／预告／禁令）再分出·边界：禁令式重踩最少（R 中位 0.35 对 0.55／0.60，M3·命令式不可替）——仍是记录写法的效应，不是任务成功率。

这个边界是仓库契约的一部分。请同时阅读 [STATUS.md](STATUS.md)、[EVIDENCE.md](EVIDENCE.md) 与 [docs/limitations.md](docs/limitations.md)。

## 30 秒运行

只需要 Python 3.11+，默认不联网、不读环境变量：

```bash
python3 examples/offline_demo.py
python3 examples/handoff_demo.py
python3 -m unittest discover -s tests -v
```

也可以安装为本地包（Debian／Ubuntu 系请用虚拟环境，系统 Python 有 PEP 668 保护）：

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e .
.venv/bin/fermion-garden-demo
```

`offline_demo.py` 输出初次选择、受压后的在位／移出项、任务变化后召回项与完整审计账。`handoff_demo.py` 则让两名 registry 身份在内存中交出／接收同一个 dump，展示接手前身份为空、接手方自行认领，以及两端 `agent_ref` 账数。后者不启动两个 Agent 进程，也不模拟 AgentTeams。

## 核心接口

```python
from fermion_garden import ContextItem, CtxKey

garden = CtxKey([
    ContextItem(id="error", text="timezone boundary test fails"),
    ContextItem(id="old", text="unrelated retired hypothesis"),
])

bundle = garden.select(
    task_state="repair the timezone boundary",
    target_role="fixer",
    budget=1,
)

garden.compact(
    task_state="repair the timezone boundary",
    target_role="fixer",
    budget=1,
)

recalled = garden.recall("validation says timezone boundary returns wrong value", budget=1)
```

`budget` 在 v0.1 中表示最多条目数，不假装是精确 token 预算。所有被移出项进入可恢复区，不做永久删除。

只读的全池排名（`scan`），以及落盘／回读：

```python
bundle = garden.scan("timezone", target_role="auditor")
# 池 = 在位 ∪ 可恢复，全部条目按名次进 bundle.decisions；⛔ 零状态改动，但账上留一行 operation="scan"

garden.save("ctx.json")            # 原子写：同目录临时文件 → fsync → os.replace
restored = CtxKey.load_from("ctx.json")   # format_version 不匹配 ⟹ 抛 ValueError，⛔ 不静默降级
```

每条打过分的账行都能自己复算——`rule_ref` 说用的哪条判据（带版本），`score_trace` 给出逐 token 的推导：

```python
event = next(e for e in garden.ledger.events if e.operation == "select")
event.rule_ref                       # 'bm25-lexical@1'
event.score_trace["score"]
# {'query': 'target_role=fixer; task=repair the timezone boundary',
#  'n_docs': 2, 'avg_len': 3.5, 'doc_len': 4,
#  'terms': [{'token': 'timezone', 'tf': 1, 'df': 1, 'idf': 0.6931471805599453,
#             'denominator': 2.6607142857142856, 'contribution': 0.6512792300563245}, …],
#  'unrounded_sum': 1.302558460112649, 'rounded': 1.30255846}
```

`terms` 为空列表是有意义的读数，不是缺账：**它说这条条目一个 query token 都没命中，分数来源为零。**
判据分层时 `rule_ref` 也照分——`recall` 的账行写的是 `bm25-lexical@1+d3-self-ratio@1`：
打分器身份盖不住比值与门槛，两层各自留名。

最小身份交接：

```python
sender = CtxKey()
investigator = sender.agent_registry.register("investigator")
fixer = sender.agent_registry.register("fixer")
sender.acting_agent = investigator

dumped = sender.dump(to_agent=fixer)
receiver = CtxKey.load(dumped)
assert receiver.acting_agent is None
receiver.acting_agent = fixer
```

完整可跑版本见 [`examples/handoff_demo.py`](examples/handoff_demo.py)。9 位号只做稳定引用，不编码角色或权限，也不防冒充。

## 仓库地图

```text
src/fermion_garden/       可安装的零网络核心
skills/ctx-key/           给 Agent 使用的 Skill 契约
examples/                 固定输入的机制演示与两身份离线交接
tests/                    标准库单元测试
evidence/round118/        第 118 轮冻结判词：Z 轴三臂打平（装置故障 G1 留账后沿用原表落格）
evidence/round119/        第 119 轮冻结判词：预检闸毙注（题面泄漏答案，46/46）
evidence/round120/        精选机械验证器、自造题、冻结判词与正式负结果（三臂打平）
evidence/round121/        第 121 轮冻结判词与分出结果（禁令式渲染）
evidence/round122/        第 122 轮冻结判词、分出·边界结果与脱敏逐棒账（首个预注册外部化轮次）
evidence/round123/        第 123 轮冻结判词与结果（σ 厚度 × 判定时刻拆开）
evidence/l15-game-duel/   L15 同题双臂真实任务对照（n=1，只报不判）
evidence/l16-game-duel2/  L16 工程态保护三臂对照（n=1，H16 方向性成立）
evidence/l17-pin-latest/  L17/L18 pin_latest 工程态保护与重放等价 12/12
evidence/s0-shop-shift/   S0 店铺客服班：52 点手写虚构流，三臂同流逐字并排（⛔ 复现边界见其 README）
evidence/jddc-185-context-growth/  322 条真实客服流上默认压缩零触发的逐 turn token 账（⛔ 只发数不发料）
evidence/early-experiments/  早期可恢复驱逐佐证（脱敏摘录）
docs/                     方法、限制、公开边界与来源说明
```

## 设计纪律

1. 上下文更短不是成功；任务结果不降或变好才是成功。
2. 判据缺失、分数无区分力或必要项超过预算时，宁可不擦并报告冲突。
3. `compact` 只改变在位状态，不能永久删除候选内容。
4. `recall` 必须留下触发理由；任务变化与验证失败都可以触发。
5. 修复者不能给自己的补丁发合格证。身份归因只让账回答“是谁”，不回答“该谁”；真正的三 Agent 闭环仍待 AgentTeams 接入。

## 来源与证据

当前 API 是从两类已运行实验整理出的最小产品边界：早期“位置受压、可逆移出、任务变化后回填”的流式装置，以及第 120 轮“最近历史／全量或压缩／动态选择”的修虫对照实验。整理后的离线词面基线是新接口，不把它冒充成第 120 轮原样代码或已验证收益。

第 118–122 轮的冻结落点与正式结果位于 [evidence/round118](evidence/round118)–[evidence/round122](evidence/round122)：一轮预检闸毙注（119）、两轮打平（118、120）、两轮分出（121 分出、122 分出·边界）。自第 122 轮起，「见数前冻结」以公开提交时间戳外部化，并随轮公开脱敏逐棒账（`per-round-account.csv`，第三方可重算 R／Z），流程见 [docs/preregistration.md](docs/preregistration.md)。这些目录不包含模型 transcript、API 凭证、私人会话或全量实验历史。

## License

MIT。实验数据与外部材料不因代码许可证自动获得再发布权；本仓库只保留自造题与精选结果。
