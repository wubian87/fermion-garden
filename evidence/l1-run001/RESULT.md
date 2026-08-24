# L1 跑 · 收口落账（2026-08-19）

## 落格：**格甲 —— 跑通且可查**（甲-1～4 全过）

⚠️ 观测单位＝一次完整流程，重数＝1 ⟹ 本跑只能否证、不能证实。
**本跑只许读成「压力→可逆擦除→验证失败→召回 这一圈至少能真实发生一次」，⛔ 不许读成「机制成立」。**

| 判据 | 结果 | 机械证据 |
|---|---|---|
| 甲-1 真实挤压 | ✅ | `selfcheck.json`：evicted 5 条非空；开放位 3（budget 4 − pinned 1）< 非强制候选 8；compact conflict=null。切割线在非强制第 3 名 index-bloat(8.512081) 与第 4 名 api-token(5.343240) 之间。 |
| 甲-2 真实失败 | ✅ | `verdict.json`：判定器独立子进程（不 import 引擎、只读期望表与答卷两文件，静态核过），断网 fail-closed（本机 unshare -n EPERM ⟹ 进程内 socket 拒绝＋武装自检，方式如实记入输出），两遍判卷逐题一致，判 3/5：Q1/Q3 未过。 |
| 甲-3 真实召回 | ✅ | `trace.jsonl`：recall 召回 {charset-mismatch, db-password, disk-quota} ⊆ 步 2 evicted 集；两条未过题的答案条（Q3→charset-mismatch、Q1→db-password）均被召回，item_id 与账机械对上。 |
| 甲-4 可查性（外包） | ✅ | `outside-audit.md`＋`outside-audit-check.json`：独立子代理只读三件套，两问四项指认（擦除步 trace_id／被擦集／召回步 trace_id／被召回集）与 `trace.jsonl` 全中；理由引用具体分数、名次、切割线、预算与触发词，非模板句。 |

## 与事前预判对账（格戊检查）

**实质全符，格戊不触发**：selected、evicted 集、失败题（Q1/Q3）、trigger 全文、recalled 三条——五项与冻结预判逐值一致（`selfcheck.json` 预判对账节）。

⚠️ 一格账面不符要写清：`selfcheck.json`「evicted名次序」记 false，**是自检比对代码的笔误**——它拿 8 名全排表去对预判的 5 名擦除表。按正确口径（擦除区＝非强制第 4–8 名），实际 [api-token, charset-mismatch, db-password, meeting-notes, disk-quota] 与预判逐值相同。跑后导出物不回改，笔误照实留在账上，判读以本节为准。

## 过程账（全值域照记）

- **冻结#1 作废重开（跑动之前）**：实测本机 `unshare -n` EPERM（沙箱内外各一次）⟹ 冻结#1「缺 unshare 即拒判」照跑必死格丙；按「改任何一项⟹作废重开」走重开，仅改判定器断网实现，料/题/参数/预判逐字节未动（机器核过）。EVENTS.md 事件 4–5。
- **首跑判卷链崩溃（fail-closed 正常履职）**：runner 把答卷写成对象、validator 按裸列表迭代 ⟹ TypeError ⟹ 判卷链失败 exit 1，**未判出任何结果**；修复＝答卷只写裸列表（判定器输入最小化），正式跑从头完整重走（非续跑、非挑参重试）。崩溃现场存 `verdict.first-run-crash.json`。EVENTS.md 事件 6–8。
- **格丁检查**：召回含一条噪声（disk-quota，与触发词仅「临/临时/新/时/间」单字碰撞得 4.64 分）——两条答案条均已召回，甲-3 成立，不落格丁；噪声召回照实在 `timeline.md`「照实记」段。

## 判卷人「账的够用程度」清单（甲-4 过了，但它点出的边界照录——下一步最值钱的输入）

1. **pinned 无机器字段**：pin-window 得 1.39 分低于 4 条被擦条却被 keep，ledger/trace 无「强制席」字段，单看账呈现分数矛盾，全靠 timeline 人读判词解释。
2. **账内无条目原文**：只有 sha256 指印；「为什么召回」的词面对应（触发词↔内容重合）无法只凭账独立验证，全靠 timeline 的重合词表。
3. **触发词链路在引擎外**：ledger 只有最终 criterion 字符串；判卷细节（哪题未过、锚词无命中、机械拼接）在 verdict/answers 两文件，不在三件套内。
4. **引擎层 reason 全是模板句**（engine.py:261/305 两句，按禁令②未动）；逐条「为什么」＝score＋导出层判词拼接——这正是「判词长在导出层」的代价与设计。

## 合规核验

- 禁令①：未 push——本地 main 领先 origin/main 4 个 commit（开工冻结／冻结#2／跑完落盘／甲-4 判卷＋本收口）。
- 禁令②：`git diff a082797..HEAD -- src/ tests/ examples/` 为空——engine/ledger/models/lexical 与现有测试、示例零改动；reason 两句模板词原样未动。
- 禁令③：验证失败由独立判定器真判出（3/5，两遍一致）；全部参数与预判冻结在先（`preset.sha256`）；无事后调参、无挑触发词重跑（重跑仅因判卷链崩溃，崩溃时未判出任何结果，且全程留痕）。
- 已知小疵照记：timeline 中 Q2 作答显示截断至 50 字（全量在 `answers.json`）；EVENTS.md 事件 4–8 时间为分钟级粗值（标 x）。

## 产物索引

`l1run/`：预设.md（冻结#2）｜preset.json｜frozen-expectations.json｜preanalysis.py｜preset.sha256｜validator.py｜run_l1.py｜audit_check.py｜EVENTS.md
`evidence/l1-run001/`：ledger.jsonl｜trace.jsonl｜timeline.md｜items.json｜answers.json｜verdict.json｜selfcheck.json｜outside-audit.md｜outside-audit-check.json｜verdict.first-run-crash.json｜RESULT.md（本文件）

---

## ⛔⛔ 限度补一条（2026-08-19 核账落刀）——原文只写了「重数＝1」，⛔ 不够

> **这一跑证明的是「这一圈能走通」，⛔ 不是「系统会自己撞上需要召回的情形」。**

**来路**：`l1run/预设.md:22` 事前写死 —— *失败是结构保证的：5 条答案条争 3 个开放位（budget 4 − pinned 1）⟹ 至少 2 条答案条必然被擦 ⟹ 判定器必然判「不过」*。

✅ **做法正当，⛔ 不是造假**：必然性事前写明（没假装是自然涌现）、判定器独立真判、值域仍写全（`预设.md:69` 写了「若判定为全过（结构上不可能，但值域要写全）」）。
⛔ **但它划死了这一跑能读出什么**：**压力和失败都是设计成必然的** ⟹ **⛔ 不许读成「这套机制会自己发现该召回」。**
⚠️ **在 L1 这么设计是对的**（否则跑十次可能一次都不失败），**代价就是这条限度。**

## ⭐ 白拿的一个真实缺陷（行为层，⛔ 不是记账层）

**召回三条的分数**：`charset-mismatch 24.21` ／ `db-password 19.95` ／ **`disk-quota 4.64`（噪声，只碰了「临／时／间」三个单字）**
⟹ **差 4.3 倍，噪声照样过门槛。**

**病根**：`src/fermion_garden/engine.py:295` —— `recalled = tuple(... if scores[item.id] > 0)[:budget]`
⟹ ⛔ **`> 0` 这个门槛是空的：任何单字碰撞都过。**

⚠️ **它比判卷人那四条「账缺什么」更硬**：**recall 的语义是「把当时错删的捞回来」，捞回噪声等于把压力又加回去** ⟹ **直接对着 y 的前半句（自己转起来）。**
⟹ ⭐ **而它是这一跑白拿的：不跑就不知道那个门槛是空的。**

⛔ **怎么修是选择式落点，⛔ 不由跑的人定、⛔ 不由写代码的人定** ——
⟹ **门槛该由零信息基线给**（必答项 ⑬）：**拿一个随机触发词跑同一批可恢复条目，看它能召回几条、分数分布在哪 —— 那个分布的上沿就是门槛，⛔ 别拍一个数。**

## ⭐ 判卷人那四条里最要紧的一条

**`pin-window` 1.39 分低于 4 条被擦条却留位 ⟹ 单看账是分数矛盾。**
**病根不是缺一个字段，是账把「规则」和「分数」混在一个维度上呈现** —— **pinned 是规则、score 是排序，混在一张表里必然自相矛盾。**

## ✅ 一条被独立验证的设计判断

**判卷人（没参与这次跑、只读三件套）交回**：*靠三件套能复算出切割线和召回排序，「为什么」说得清。*
⟹ **「判词长在导出层、⛔ 不长在引擎里」这个设计成立** —— **而且它是外包判的，⛔ 不是自评。**
