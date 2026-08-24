# L1 跑 · 人读时间线（导出层判词；引擎只出分数与模板句，判词在这层拼装）

- 跑时：2026-08-19T11:10:17.868411+00:00（UTC）· 3.12.3 · 断网方式：unshare-eparm→in-process-socket-denial
- 场景：数据库迁移值班交接。9 条候选料进入上下文（1 条 pinned 约束），5 题问卷为任务，独立判定器判卷。

## 步 1 · record（trace_id=77533682a3834fbb925cf0fbeaa609fc，context_version→1）

9 条全部进入在位上下文，无挤压。判词：初始交接，来料全收；压力尚未出现。

## 步 2 · compact（trace_id=999ff86cd8d248aa95ed8c7b9c2ea6a4，context_version→2）：真实挤压

- 任务态（criterion）：执行数据库迁移前的检查与回滚准备
- 预算 4 ＝ 强制 1 条（pinned：pin-window）＋ 开放位 3 个；当时非强制候选 8 条 > 3 ⟹ 必须挤。
- 逐条（分数＝该任务态下 BM25 词面分；排名＝非强制内按分数、created_at、id）：

| 排名 | id | 分数 | 去向 | 与任务态词面重合 |
|---|---|---|---|---|
| 1 | rollback-plan | 15.347170 | 留（开放位内） | 前、回、回滚、执、执行、滚、移、行、迁、迁移 |
| 2 | replica-lag | 9.016872 | 留（开放位内） | 库、执、执行、查、检、检查、行 |
| 3 | index-bloat | 8.512081 | 留（开放位内） | 前、查、检、检查、移、移前、迁、迁移 |
| 4 | api-token | 5.343240 | 擦（可逆移出） | 查、检、检查、的 |
| 5 | charset-mismatch | 4.556228 | 擦（可逆移出） | 备、库、移、迁、迁移 |
| 6 | db-password | 2.966990 | 擦（可逆移出） | 库、移、迁、迁移 |
| 7 | meeting-notes | 2.964262 | 擦（可逆移出） | 与、移、迁、迁移 |
| 8 | disk-quota | 0.000000 | 擦（可逆移出） | （无） |
| — | pin-window | 1.394523 | 留（pinned 强制） | 移、迁、迁移 |

- 切割线判词：开放位 3 个，非强制第 3 名 index-bloat（8.512081）留下，第 4 名 api-token（5.343240）起的 5 条全部可逆移出——移出不是删除：条目原文仍在可恢复区，其内容 sha256 已随决策进账（见 ledger.jsonl / items.json）。

- 被擦逐条判词：api-token（5.343240，非强制第 4 名）；charset-mismatch（4.556228，非强制第 5 名）；db-password（2.966990，非强制第 6 名）；meeting-notes（2.964262，非强制第 7 名）；disk-quota（0.000000，非强制第 8 名）。

## 步外 · 独立判定（外部事件，不是引擎操作）

- 交付上下文（compact 后在位）：pin-window、rollback-plan、replica-lag、index-bloat
- Q1未过（作答：（交接上下文中无法作答））；Q2过（作答：回滚方案：如果迁移在 03:00 前未完成校验，立即执行 pg_restore 回滚到快照 snap）；Q3未过（作答：（交接上下文中无法作答））；Q4过（作答：从库复制延迟超过 30 秒时禁止切换流量，先执行 pg_rewind 再检查 wal_receive）；Q5过（作答：索引膨胀检查：orders 表 pg_repack 需要 40 分钟，必须安排在迁移后而不是迁移前）
- 判定器判卷：过题数 3/5，两遍一致（确定性=True），断网方式＝unshare-eparm→in-process-socket-denial。判定器只见答卷与期望表，不见引擎状态、料序与账。
- 触发词（机械生成：未过题面按题号升序「；」拼接）：**迁移期间主库的临时密码是什么？；旧库 latin1 新库 utf8mb4，迁移脚本必须带哪个转换参数？**

## 步 3 · recall（trace_id=8eadd3aaeb1248e39163d83ef3919901，context_version→3）

- 触发词：迁移期间主库的临时密码是什么？；旧库 latin1 新库 utf8mb4，迁移脚本必须带哪个转换参数？
- 召回预算 3；对可恢复区 5 条按触发词打分，取分数>0 的前 3 名：

| 排名 | id | 分数 | 与触发词词面重合 | 去向 |
|---|---|---|---|---|
| 1 | charset-mismatch | 24.212118 | latin1、utf8mb4、带、库、必、必须、新、新库、旧、旧库、是、本、本必、移、移脚、脚、脚本、迁、迁移、须、须带 | 召回 |
| 2 | db-password | 19.952400 | 临、临时、主、主库、密、密码、库、换、时、期、期间、码、移、移期、迁、迁移、间 | 召回 |
| 3 | disk-quota | 4.635676 | 临、临时、新、时、间 | 召回 |
| 4 | api-token | 3.938017 | 本、的、脚、脚本 | 留在可恢复区 |
| 5 | meeting-notes | 2.031336 | 本、移、迁、迁移 | 留在可恢复区 |

- Q1 在步 2 后交付上下文中锚词「只读密码」无命中（答案条 db-password 已被可逆移出）⟹ 无法作答 ⟹ 未过；本步 db-password 以 19.952400 分被召回，锚词回到在位上下文——召回的正是步 2 擦掉的那条（evicted∩recalled 可在账中机械核对）。
- Q3 在步 2 后交付上下文中锚词「utf8mb4」无命中（答案条 charset-mismatch 已被可逆移出）⟹ 无法作答 ⟹ 未过；本步 charset-mismatch 以 24.212118 分被召回，锚词回到在位上下文——召回的正是步 2 擦掉的那条（evicted∩recalled 可在账中机械核对）。
- 照实记：disk-quota（非任一未过题的答案条）因与触发词词面重合（临、临时、新、时、间）得 4.635676 分 > 0，在召回预算内一并被带回——召回按词面分排序，不带「该不该」的判断。

## 末态

- context_version=3；在位 pin-window、rollback-plan、index-bloat、replica-lag、charset-mismatch、db-password、disk-quota；可恢复区 api-token、meeting-notes（原文保留，未删除）。

## 账目指针

- 逐条决策账：`ledger.jsonl`（每条 Decision 一行：分数/理由/criterion/budget/内容sha256）
- 引擎步骤原貌：`trace.jsonl`（record 摘要行＋compact/recall 的 bundle 全量）
- 候选全文与哈希对账：`items.json`
- 判卷原始输出：`verdict.json`；作答过程：`answers.json`
