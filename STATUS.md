# Status

证据数据截点：2026-08-17，第 118–122 轮均已正式落格并精选入库（118 打平、119 预检闸毙注、120 打平、121 分出、122 分出·边界）。第 122 轮为首个冻结时序外部化轮次：冻结表先于跑数推送（commit ee029ab），结果侧导出含脱敏逐棒账，见 `docs/preregistration.md`。产品接口截点：2026-08-24，L14.1 单进程身份归因与 handoff 审计已经落码；这不改变前述实验结论。初赛提交时点为 37 个跟踪文件，此后提交均为维护与证据补全。

| 能力 | 状态 | 可核位置 |
|---|---|---|
| `select / compact / recall` 稳定接口 | 已实现，v0.1 词面基线 | `src/fermion_garden/engine.py` |
| 可逆移出与召回 | 已实现 | `tests/test_engine.py` |
| 判词、版本、`trace_id` 审计 | 已实现 | `src/fermion_garden/ledger.py` |
| 零网络演示 | 已实现 | `examples/offline_demo.py` |
| 9 位参与者身份与账行 `agent_ref` | 已实现，单进程 | `src/fermion_garden/agents.py`、`tests/test_engine.py` |
| dump/load handoff 两端审计 | 已实现；接手方须自行设置 `acting_agent` | `examples/handoff_demo.py`、`l141run/报告.md` |
| Skill 使用契约 | 已实现初版 | `skills/ctx-key/SKILL.md` |
| 第 118–122 轮机械验证证据 | 已精选 | `evidence/round118/`–`evidence/round122/` |
| 第 122 轮（死路记录写法三臂：尺/画/禁） | 已落格：M3·命令式不可替（两开格对皆分出·边界），脱敏逐棒账已公开 | `evidence/round122/` |
| 第 123 轮（σ 厚度×判定时刻拆开：双臂 10 vs 31） | 已落格：M4 零机会打平＋σ31 S2＋σ10 技术性不完备（σ 薄的代价＝早窗换 y 遇模型拒绝） | `evidence/round123/` |
| L15 同题双臂真实任务对照（雾井地牢） | 已跑数（n=1）：乙臂（CtxKey B=6）终轮提示为直推臂 1/20、客观项不劣（O2/O4 乙优、甲带验收器限度星号）；判词待盲评合成，不构成成功率证明 | `evidence/l15-game-duel/` |
| 早期可恢复驱逐证据（18/18 vs 11/18）与两次撤回摘录 | 已精选、脱敏 | `evidence/early-experiments/reversible-eviction.md` |
| AgentTeams 适配器 | 未实现 | 不在仓库中 |
| 消息总线与分布式 Trace | 未实现 | handoff 目前只是 dump 内的审计块 |
| 三职能 Agent 运行闭环 | 未实现 | 只有设计，不冒充代码 |
| 嵌入与模型 provider | 未整理进公开核心 | 私人实验使用过，公开核心默认零网络 |
| 生产安全沙箱 | 未实现 | 第 120 轮验证器只用于受控实验 |
| 任务成功率收益 | 未证明 | 第 120 轮三臂打平；第 121 轮量出的是死路记录写法效应（R 0.55 对 0.65，Z 双 0.90 打平），不是成功率收益；第 122 轮三臂量出的是渲染写法效应（禁 0.35 对尺 0.55／画 0.60，M3·命令式不可替），也不是成功率收益 |

## 版本含义

- `0.1`：本地词面检索、可恢复账、稳定 Schema、单进程身份归因与离线测试。
- `0.2`：计划加入可替换嵌入与判据 provider，必须重新做基线对照。
- `0.3`：计划加入 AgentTeams 交接适配和跨 Agent Trace，不能提前写成已完成。
