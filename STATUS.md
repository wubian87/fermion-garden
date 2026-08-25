# Status

**证据数据截点：2026-08-25。**第 118–123 轮均已正式落格并精选入库（118 打平、119 预检闸毙注、120 打平、121 分出、122 分出·边界、123 M4 零机会打平＋σ31 S2）；此后 L15／L16 真实任务对照（各 n=1）、L17／L18 `pin_latest` 与重放等价、S0 店铺客服班三臂同流依次入库。第 122 轮为首个冻结时序外部化轮次：冻结表先于跑数推送（commit ee029ab），结果侧导出含脱敏逐棒账，见 `docs/preregistration.md`。

**产品接口截点：2026-08-25（L18）。**引擎侧已落码到 `select / compact / recall / scan` 四操作 ＋ `pin_latest` ＋ `save / load_from` ＋ 规则身份与逐 token 打分留痕 ＋ 单进程身份归因与 handoff 审计。这些都不改变前述实验结论——**接口做完不等于收益被证明**，「尚未证明」那几行照旧立着。

初赛提交时点为 37 个跟踪文件，此后提交均为维护与证据补全。

| 能力 | 状态 | 可核位置 |
|---|---|---|
| `select / compact / recall / scan` 稳定接口 | 已实现，v0.1 词面基线（`scan`＝全池排名，只读、零状态改动，账上仍留一行 `operation="scan"`） | `src/fermion_garden/engine.py`、`tests/test_scan_l125.py` |
| 可逆移出与召回 | 已实现 | `tests/test_engine.py` |
| 判词、版本、`trace_id` 审计 | 已实现 | `src/fermion_garden/ledger.py` |
| **打分可被第三方独立复算** | 已实现：账行带 `rule_ref`（判据身份含版本，如 `bm25-lexical@2`）与 `score_trace`（query、`n_docs`、`avg_len`、`doc_len`、逐 token 的 `tf/df/idf/denominator/contribution`、`unrounded_sum`、`rounded`）⟹ 拿账行就能把分自己算一遍，不用相信引擎 | `src/fermion_garden/ledger.py`、`src/fermion_garden/lexical.py` |
| **落盘与回读（`save` / `load_from`）** | 已实现（L10.1）：原子写（同目录临时文件 → `fsync` → `os.replace`），带 `format_version`；**版本不匹配一律抛 `ValueError` 拒读，⛔ 不静默降级、⛔ 不尽力而为地读**。⚠️ 掉电级的目录项 `fsync` 未做 | `src/fermion_garden/engine.py`（`save`／`load_from`／`_format_version`） |
| 零网络演示 | 已实现 | `examples/offline_demo.py` |
| 9 位参与者身份与账行 `agent_ref` | 已实现，单进程 | `src/fermion_garden/agents.py`、`tests/test_engine.py` |
| dump/load handoff 两端审计 | 已实现；接手方须自行设置 `acting_agent` | `examples/handoff_demo.py`、`l141run/报告.md` |
| Skill 使用契约 | 已实现初版 | `skills/ctx-key/SKILL.md` |
| 第 118–122 轮机械验证证据 | 已精选 | `evidence/round118/`–`evidence/round122/` |
| 第 122 轮（死路记录写法三臂：尺/画/禁） | 已落格：M3·命令式不可替（两开格对皆分出·边界），脱敏逐棒账已公开 | `evidence/round122/` |
| 第 123 轮（σ 厚度×判定时刻拆开：双臂 10 vs 31） | 已落格：M4 零机会打平＋σ31 S2＋σ10 技术性不完备（σ 薄的代价＝早窗换 y 遇模型拒绝） | `evidence/round123/` |
| L15 同题双臂真实任务对照（雾井地牢） | 已收口（n=1）：判词「部分（只报不判）」——乙臂供给 1/20 且客观不劣，主观盲评甲臂优（ΣS 12:9）；逐轮取证 4/4 相关：代码条目被挤出活动区的轮次工程态蒸发（黄铜钥匙丢失），需求承载的冻结约束全程守住。不构成成功率证明 | `evidence/l15-game-duel/` |
| `CtxKey.pin_latest(source)` 工程态保护 | 已实现（L17）＋重放等价（L18）：离线重放 L16 丙臂 12 轮，活动区与当时提示逐值一致 12/12——API 与已验证策略同轨 | `src/fermion_garden/engine.py`、`tests/test_pin_latest_l17.py`、`evidence/l17-pin-latest/` |
| L16 工程态保护三臂对照（雾井地牢·二轮） | 已收口（n=1）：K1–K5 全过，**H16 成立（方向性）**——最新代码 pinned 使三钥完备 35/36（对照 29/36 且终版带伤）、ΣS 追平直推 12:12、供给保持 36%/22.5%。引擎层 API 未实现，不构成成功率证明 | `evidence/l16-game-duel2/` |
| 早期可恢复驱逐证据（18/18 vs 11/18）与两次撤回摘录 | 已精选、脱敏 | `evidence/early-experiments/reversible-eviction.md` |
| S0 店铺客服班三臂同流（52 点手写虚构流，2026-08-25） | 已跑完（n=1、单跑）：四类陷阱三臂全对、丢单三臂皆 0；**② 全赢照预注册报**（52 点太短，压缩三臂 0 次触发，长班糊化未测到）。⛔ 原始 373 发回复账未上传 ⟹ 只支持拿同一份公开料复做结构相同的新运行，**不支持复现原始结果** | `evidence/s0-shop-shift/` |
| 322 条真实客服流上默认压缩零触发（对照读数） | 已复算：触发 0 次，单 turn 请求量涨到 70,867（cacheRead 70,784）。⛔ 料受 JDDC 许可约束不发布，只发布逐 turn 计数＋源账 sha256 | `evidence/jddc-185-context-growth/` |
| AgentTeams 适配器 | 未实现 | 不在仓库中 |
| 消息总线与分布式 Trace | 未实现 | handoff 目前只是 dump 内的审计块 |
| 三职能 Agent **产品化**运行闭环 | 未实现 | 引擎层只有设计，不冒充代码。⚠️ 说准一处：`evidence/s0-shop-shift/` 里确有一次三角色（分诊／办理／审核）真实调用运行，但它跑在**一次性实验脚本**里，不是本仓引擎的产品接口，也不是 AgentTeams 闭环 |
| 「AI 自动运营店铺」 | 未实现 | 本仓只到「受控客服班上验证分诊／办理／审核的上下文交接结构」；定价、库存、履约、支付一概不碰 |
| 嵌入与模型 provider | 未整理进公开核心 | 私人实验使用过，公开核心默认零网络 |
| 生产安全沙箱 | 未实现 | 第 120 轮验证器只用于受控实验 |
| 任务成功率收益 | 未证明 | 第 120 轮三臂打平；第 121 轮量出的是死路记录写法效应（R 0.55 对 0.65，Z 双 0.90 打平），不是成功率收益；第 122 轮三臂量出的是渲染写法效应（禁 0.35 对尺 0.55／画 0.60，M3·命令式不可替），也不是成功率收益 |

## 版本含义

- `0.1`：本地词面检索、可恢复账、稳定 Schema、单进程身份归因与离线测试。
- `0.2`：计划加入可替换嵌入与判据 provider，必须重新做基线对照。
- `0.3`：计划加入 AgentTeams 交接适配和跨 Agent Trace，不能提前写成已完成。
