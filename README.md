# 费米子乐园 / Fermion Garden

> Research preview: an auditable, reversible context selector for multi-agent handoffs.

**GOAI Agent Infra 初赛仓库。** 参赛名「**费米子乐园·八爪鱼**」：费米子乐园＝共享上下文环境与 `ctx-key` Skill；八爪鱼＝住在其中、完成软件修复任务的三职能 Agent 团队（诊断／修复／验证，设计阶段，AgentTeams 接入未完成）。

参赛主体：重庆伴月之星网络科技有限公司 · [byzx.xyz](https://byzx.xyz)。评委请以本仓库、方案文档和 500 字简介为准；官网是公司主页，不是本赛的运行证据。

评委或 AI 请先读：`README.md` → `STATUS.md` → `EVIDENCE.md` → `examples/offline_demo.py`。不要把本仓库读成已完成的多 Agent 产品。

多 Agent 共用的上下文会持续增长。费米子乐园把“下一位 Agent 这一步该读什么”做成三个显式操作：`select` 选择、`compact` 可逆移出、`recall` 按新证据召回。每次决定都留下理由、版本与 `trace_id`。

L14.1 还加入了单进程的 `AgentRegistry`：给参与者发 9 位号，让账行带 `agent_ref`，并在 `dump(to_agent=...)` 中记录一次 handoff 的两端。它是可审计的身份归因，不是权限系统、消息总线或 Agent 调度器；接手方 `load` 后必须自己设置 `acting_agent`，旧钥匙不会替它冒充身份。

## 当前状态

这是从私人实验母库白名单提取的初赛代码候选，不是完成品。

- **已实现**：零网络词面基线；`select / compact / recall` 与 `pin_latest` 工程态保护（版本化材料的最新态钉在活动区，`protect` 账行）；可恢复账本；单进程参与者身份、账行归因与 handoff 审计；两个离线演示；单元测试；第 120–122 轮机械证据快照与 L15–L16 真实任务对照证据。
- **尚未实现**：AgentTeams 适配器、消息总线、分布式 Trace、真实的 `investigator / fixer / verifier` 三 Agent 运行闭环、嵌入 provider、生产沙箱。
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
