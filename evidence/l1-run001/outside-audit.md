# 甲-4 · 外包判卷（2026-08-19）

判卷人：一个没参与本次跑的模型（独立子代理，无本次跑的任何上下文）。
输入：只有三件套——`ledger.jsonl`、`trace.jsonl`、`timeline.md`（⛔ 未给代码、未给预设.md、未给 items.json/verdict.json/answers.json/跑的过程）。
任务原文与答案原文如下，一字未改。

---

## 判卷人答案（原文）

## 问一
- 擦除步 trace_id: 999ff86cd8d248aa95ed8c7b9c2ea6a4（operation=compact，context_version→2）
- 被擦 item_id 列表: api-token, charset-mismatch, db-password, meeting-notes, disk-quota
- 逐条理由:
  - 先说切割线怎么立的（依据 ledger 的 budget=4 与 criterion、trace 的 selected_ids/evicted_ids、timeline 的「预算 4＝强制 1 条（pinned：pin-window）＋开放位 3 个」）：9 条候选中 8 条非强制竞争 3 个开放位，按 criterion「执行数据库迁移前的检查与回滚准备」下的 BM25 词面分排序，第 3 名 index-bloat（8.512081）是最后留下的，切割线落在第 3 名（8.512081）与第 4 名 api-token（5.343240）之间；第 4 名起全部落在可逆移出一侧。注意 pin-window 虽只有 1.394523 分（低于 4 条被擦条目）却被 keep，ledger 单看分数自相矛盾，只有 timeline 的「pinned 强制占 1 席、不参与排名」能解释——即切割线只对非强制 8 条生效。
  - api-token: 非强制第 4 名，score=5.343240（ledger seq 13，action=evict）。低于第 3 名 index-bloat 的 8.512081，排在 3 个开放位之外；timeline 词面重合列显示它与任务态只重合「查、检、检查、的」，其中「的」是虚词，实义重合仅「检查」一词，不足以挤进前 3。
  - charset-mismatch: 非强制第 5 名，score=4.556228（seq 14）。与任务态重合「备、库、移、迁、迁移」，全是「迁移」一词的通用字/子词，无「检查/执行」类词，词面分低于切割线。
  - db-password: 非强制第 6 名，score=2.966990（seq 15）。重合仅「库、移、迁、迁移」，同为迁移泛词，分更低。
  - meeting-notes: 非强制第 7 名，score=2.964262（seq 16）。重合「与、移、迁、迁移」，与 db-password 仅差 0.0027（并列边缘，两者都被擦，未动用 tie-break）。
  - disk-quota: 非强制第 8 名（末名），score=0.000000（seq 18）。timeline 词面重合列为「（无）」——与任务态零词面重合，BM25 得 0 分，垫底必擦。
  - 补一句账中明载的定性：这些 evict 均是可逆移出而非删除，每条的 item_content_sha256 随决策进了 ledger（timeline「切割线判词」段）。
- 判定依据的字段: ledger.jsonl 的 action（evict）、score、budget（=4）、criterion、sequence、item_content_sha256、trace_id；trace.jsonl 第 2 行 bundle 的 budget、criterion、decisions[]、evicted_ids、selected_ids；timeline.md 的「预算 4＝强制 1＋开放 3」「排名＝非强制内按分数、created_at、id」「分数＝BM25 词面分」及逐条词面重合表与切割线判词。

## 问二
- 召回步 trace_id: 8eadd3aaeb1248e39163d83ef3919901（operation=recall，context_version→3）
- 被召回 item_id 列表: charset-mismatch, db-password, disk-quota
- 触发原因（账里怎么写的）: ledger criterion 字段原文「迁移期间主库的临时密码是什么？；旧库 latin1 新库 utf8mb4，迁移脚本必须带哪个转换参数？」；其来历 timeline「步外」段有记：这是步 2 之后独立判定器判卷、Q1/Q3 未过（在位上下文中锚词「只读密码」「utf8mb4」无命中，因答案条已被擦），“未过题面按题号升序『；』拼接”机械生成触发词——即触发来自外部判定事件，不是引擎自发。
- 逐条理由（召回规则＝timeline 所记「对可恢复区 5 条按触发词打分，取分数>0 的前 3 名」，预算 3 见 ledger/trace 的 budget 字段；可恢复区恰为步 2 擦掉的 5 条，recalled_ids ⊆ 步 2 evicted_ids，账中可机械核对）:
  - charset-mismatch: score=24.212118，第 1 名（ledger seq 19）。与触发词词面重合最厚（latin1、utf8mb4、旧库、新库、脚本、必须、须带等——timeline 重合列），正对触发词第二问「latin1→utf8mb4 转换参数」；它正是 Q3 的答案条，Q3 未过就因它在步 2 被擦。
  - db-password: score=19.952400，第 2 名（seq 20）。重合临、临时、主库、密码、期间等，正对触发词第一问「临时密码」；它是 Q1 的答案条，Q1 未过同理。
  - disk-quota: score=4.635676，第 3 名（seq 21）。仅因与触发词碰上「临、临时、新、时、间」这些单字/短子词得分 4.635676>0，且预算 3 内有空位，被顺带带回。
  - （对照）api-token 3.938017、meeting-notes 2.031336 排第 4、5 名，ledger action=retain「not recalled for this trigger」，留在可恢复区。
- 与触发原因无关却被召回的条目（若有）: disk-quota——timeline「照实记」明写它「非任一未过题的答案条」，被召回纯因词面分排序的机械结果（「召回按词面分排序，不带『该不该』的判断」）；它与两个未过题的语义无对应，重合字（时/间/新等）是「期间/临时/新库」的偶然单字碰撞。真正与触发原因对应的是前两条 charset-mismatch、db-password。

## 账的够用程度
- 说得清的：两步各擦/召了谁、每条的分数、预算、criterion、以及排序位置——ledger 逐行可核对；「擦谁不擦谁」的切割线可由 ledger 分数＋trace 的 budget/selected_ids 复算出来（唯一例外见下）；召回的 top-3 与分数排序也完全可复算；evicted∩recalled 可机械验证「召回的正是步 2 擦掉的」。
- 说不清／要靠 timeline 补的：① pin-window 低分却 keep——ledger/trace 无任何「pinned/强制席」机器字段，全凭 timeline 一句人读判词，账本身呈现分数矛盾；② 「分数是 BM25 词面分」及每条的重合词清单只在 timeline，条目原文账里只有 sha256（items.json 不许读），词面重合无法独立验证；③ 召回触发词的生成链路（Q1/Q3 未过、锚词无命中、机械拼接）是引擎外事件，ledger/trace 只有最终 criterion 字符串，判卷细节在未提供的 verdict.json/answers.json；④ ledger 的 reason 全是模板短句（"reversibly moved under budget pressure"/"matched recall trigger"），引擎层无逐条具体理由，逐条「为什么」全靠 score＋timeline 判词拼接——timeline 自己也声明「引擎只出分数与模板句，判词在这层拼装」。缺的东西：条目原文与哈希对账文件（items.json）、判卷原始输出（verdict.json/answers.json）、以及 trace 里的 pinned 标记与打分/排序配置的机器字段；有了前两类才谈得上独立复核，有了第三类 compact 的低分 keep 才不靠人读层解释。

---

## 机械比对（甲方执行，脚本 `l1run/audit_check.py`，结果见 `outside-audit-check.json`）

比对项：判卷人所报「擦除步 trace_id／被擦 item_id 集／召回步 trace_id／被召回 item_id 集」四项，逐一与 `trace.jsonl` 实际值比对；「理由是否超出模板句」按其是否引用了该步具体数值（分数/名次/切割线/预算/触发词）判。
