# Status

数据截点：2026-08-16，第 120 与 121 轮均已正式落格并精选入库；第 122 轮在途，未进入本副本。

| 能力 | 状态 | 可核位置 |
|---|---|---|
| `select / compact / recall` 稳定接口 | 已实现，v0.1 词面基线 | `src/fermion_garden/engine.py` |
| 可逆移出与召回 | 已实现 | `tests/test_engine.py` |
| 判词、版本、`trace_id` 审计 | 已实现 | `src/fermion_garden/ledger.py` |
| 零网络演示 | 已实现 | `examples/offline_demo.py` |
| Skill 使用契约 | 已实现初版 | `skills/ctx-key/SKILL.md` |
| 第 120／121 轮机械验证证据 | 已精选 | `evidence/round120/`、`evidence/round121/` |
| 早期可恢复驱逐证据（18/18 vs 11/18）与两次撤回摘录 | 已精选、脱敏 | `evidence/early-experiments/reversible-eviction.md` |
| AgentTeams 适配器 | 未实现 | 不在仓库中 |
| 三职能 Agent 运行闭环 | 未实现 | 只有设计，不冒充代码 |
| 嵌入与模型 provider | 未整理进公开核心 | 私人实验使用过，公开核心默认零网络 |
| 生产安全沙箱 | 未实现 | 第 120 轮验证器只用于受控实验 |
| 任务成功率收益 | 未证明 | 第 120 轮三臂打平；第 121 轮量出的是死路记录写法效应（R 0.55 对 0.65，Z 双 0.90 打平），不是成功率收益 |

## 版本含义

- `0.1`：本地词面检索、可恢复账、稳定 Schema、离线测试。
- `0.2`：计划加入可替换嵌入与判据 provider，必须重新做基线对照。
- `0.3`：计划加入 AgentTeams 交接适配和跨 Agent Trace，不能提前写成已完成。

