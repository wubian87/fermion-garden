#!/usr/bin/env python3
"""239 八爪鱼-S0（小说班臂④）：238-F 装置逐字复用，只换料（S0 手写流）与会话调度（交错班）。

⛔ 未动（与 八爪鱼-F.py 逐字同）：分诊/办理/审核提示（含用页硬规则）、窗 12、办理/审核预算 18/16、
   必带结构（店规+档案+窗+上我方终稿）、上我方终稿记条目、审核退回重试、三试重试、交接头 dump、账行格式。
与 F 的差异（全是料形差异，来源：S0 班内 8 客户交错，JDDC 是会话顺序到场）：
  · 差异①（调度）：分诊在每位客户的首点触发（F：会话切换触发）；必带0 的「上一会话档案」改为
    「最近接待客户档案」（JDDC 顺序班的『上一位』在交错班里的对应物）。
  · 差异②（收尾）：收尾 compact 推迟到班终、按各会话末点顺序逐会话补跑（F：会话末点即压——
    JDDC 会话一去不返所以安全；S0 客户还会回来，中段 compact 会把后来点的窗口条目挤出活动区，
    required-ids-not-active。DRY 第二跑咬住）。
  · 差异③（档案）：F 的全局 档案现 只在「会话顺序到场」时成立；S0 按会话各存各的（档案库）。
  · 差异④（降级算术）：select/compact 冲突降级的预算从 len(必带) 改为 len(必带∪钉集)——
    引擎 mandatory=必带∪pinned，交错班里钉着的可能是别家档案，len(必带) 装不下。
    意图不变：并列时管家只交必带件、零可选位。记忆条目文本＝料侧预生成的标记行，页内自带会话标。
    （DRY 闸 2026-08-25 首跑即咬住差异③④，零发数。）
用法：set -a; source <你自己的 .env>; set +a; python3 八爪鱼-S0.py
      JDDC239_DRY=1 零调用走全链；JDDC239_SMOKE=1 首点全链即停。
      FERMION_GARDEN_SRC=<本仓 src 的绝对路径>（不设则按本文件位置回推本仓 src）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 跑后补丁（2026-08-26，两处，逐条列明；2026-08-25 那次真跑用的是补丁前的版本）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
补丁 A（行为变了）：审核结果的解析从 **fail open 改成 fail closed**。

  补丁前（＝ 2026-08-25 真跑时跑的那几行，逐字）：
      审o = 抽JSON(审核出["回复"])
      if 审o is None:
          放行, 问题 = True, []
          审核态 = "解析失败·按放行落账"
      else:
          放行 = bool(审o.get("放行", True)); 问题 = list(审o.get("问题") or [])
          审核态 = "放行" if 放行 else "退回"

  两个洞：① 审核回复解析不出 JSON 时**直接放行**；② `bool()` 会把字符串 "false"
  这类非布尔值判成真 —— 两者都跟「审核员查账不放行问题件」这句叙述相冲突。

  这一处**没有影响 2026-08-25 那次跑的读数**，而这句话是从账上数出来的、不是推的：
      八爪鱼账S0.jsonl 里 52 个有「审核态」的点 ⟹ 放行 51 ／ 退回 1 ／ **解析失败 0**。
      （原始账未随本仓上传，见本目录 README「⛔ 原始跑数不入本仓」；上面这两个数
        可由 README 与 并排-S0.md 的「审核退回重写 1 次」逐点对上。）
  ⟹ 补丁前后在这条班上的输出**逐字相同**；补丁改的是「下一次遇到没遇到过的输入时怎么倒」。

补丁 B（行为没变）：第 24 行原先硬编码了作者本机的引擎 src 路径，改成
  环境变量 FERMION_GARDEN_SRC → 本文件位置回推 → 报错退出。纯路径解析，不碰跑法。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json, os, re, subprocess, sys, time, hashlib
from pathlib import Path

注地 = Path(__file__).resolve().parent
# 引擎 src 的位置：环境变量优先，其次按本文件在本仓中的位置回推（evidence/s0-shop-shift/ → 仓根/src）
_src = os.environ.get("FERMION_GARDEN_SRC") or str(注地.parent.parent / "src")
if not (Path(_src) / "fermion_garden" / "engine.py").is_file():
    sys.exit(f"找不到引擎 src：{_src}\n"
             f"请设 FERMION_GARDEN_SRC=<fermion-garden checkout>/src 后重跑。")
sys.path.insert(0, _src)
from fermion_garden.engine import CtxKey          # noqa: E402
from fermion_garden.models import ContextItem     # noqa: E402

料 = json.loads((注地 / "回复料-S0.json").read_text(encoding="utf-8"))
流, 点表 = 料["流"], 料["回复点"]
店规 = (注地 / "店规-S0.txt").read_text(encoding="utf-8").strip()
DRY = os.environ.get("JDDC239_DRY") == "1"
SMOKE = os.environ.get("JDDC239_SMOKE") == "1"

窗宽, 办理预算, 审核预算 = 12, 18, 16   # D1/F 参数照抄

钥匙dir = 注地 / "八爪鱼钥匙S0"
钥匙dir.mkdir(exist_ok=True)
账名 = os.environ.get("S0_账名", "八爪鱼账S0.jsonl")
账f = (注地 / 账名).open("w", encoding="utf-8")
def 落(d):
    d["时刻"] = time.time()
    账f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n"); 账f.flush()

钥匙 = CtxKey()
号 = {名: 钥匙.agent_registry.register(f"239八爪鱼S0·{名}") for 名 in ("编排", "分诊", "办理", "审核")}
钥匙.acting_agent = 号["编排"]
落({"令": "开班", "号": 号, "DRY": DRY, "SMOKE": SMOKE, "账名": 账名,
    "刀": {"窗宽": 窗宽, "办理": 办理预算, "审核": 审核预算, "上一终稿进办理必带": True, "班形": "交错8客户"}})

序 = 0
def 新序():
    global 序; 序 += 1; return 序

镜像 = {}
会话对话 = {}
我方 = {}        # 会话k → [item id…]（本会话历次办理终稿）
def 记(items, 理由):
    ids = 钥匙.record(items, reason=理由)
    for it in items:
        镜像[it.id] = it
        if it.source.endswith("·对话"):
            会话对话.setdefault(it.source[:-3], []).append(it.id)
        elif it.source.endswith("·我方"):
            我方.setdefault(it.source[:-3], []).append(it.id)
    return ids

记([ContextItem(id="店规", text=店规, source="店规", created_at=新序(), tags=("规范",))], "开店配规")
钥匙.pin_latest("店规")

def 调工人(角色, 提示):
    if DRY:
        罐头 = {
            "分诊": '{"档案": "DRY档案：客户咨询商品问题待核实", "问题类型": "商品", "紧急": "中"}',
            "办理": "DRY办理：亲，您的问题已收到，马上为您核实处理哦~\n【转人工】否",
            "审核": '{"放行": true, "问题": []}',
        }
        return {"回复": 罐头[角色], "usage": {"dry": True}, "墙钟秒": 0.0, "sessionId": f"dry-{角色}"}
    for 试 in range(3):
        if 试: time.sleep(3 * 试)
        (注地 / "工人提示-S0.json").write_text(json.dumps({"提示": 提示}, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ)
        env["DSH_HOME"] = os.environ.get("S0_工人家", str(Path.home() / ".dsh-239-a4"))
        env["DSH_233_CONFIG"] = "插件配置-S0-工人.json"
        t0 = time.time()
        r = subprocess.run(["dsh", "--profile", "工人S0"], capture_output=True, text=True,
                           env=env, cwd=str(注地), timeout=300)
        行 = (r.stdout or "").strip().splitlines()
        try:
            obj = json.loads(行[-1]) if 行 else {}
        except json.JSONDecodeError:
            obj = {}
        落({"令": "工人进程", "角色": 角色, "试": 试 + 1, "返码": r.returncode, "stderr尾": (r.stderr or "")[-300:]})
        if obj.get("回复"):
            return obj
    raise RuntimeError(f"{角色}工人三试无回复：{(r.stderr or '')[-400:]}")

def 抽JSON(文: str) -> dict | None:
    文 = re.sub(r"```(?:json)?", "", 文 or "").strip()
    m = re.search(r"\{[^{}]*\}", 文, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except json.JSONDecodeError: return None

def 交接头(d):
    b = json.dumps(d, ensure_ascii=False, sort_keys=True).encode()
    return {"handoff": d["handoff"], "context_version": d["context_version"],
            "账行数": len(d["ledger_events"]), "active": len(d["active"]),
            "recoverable": len(d["recoverable"]), "dump_sha256": hashlib.sha256(b).hexdigest()}

硬约束 = "\n\n直接以中文回复正文开头；不要输出思考过程、英文或任何前言。"
用页硬规则 = "\n（硬规则：上页已出现的订单号、客户已陈述的事实、我方已作过的承诺，一律视为已知——禁止再当作缺失向客户索要，禁止声称「您还没提供」。）"

分诊提示 = """{店规}

你是客服分诊台。班内旧案与当前新客户的首问如下。请给这位客户建档并分诊。
输出一行 JSON（不要别的）：{{"档案": "<一句话：这位客户是谁、什么问题、关键事实>", "问题类型": "<物流/售后/支付/商品/账号/其他>", "紧急": "低/中/高"}}

〔班内相关旧案（记忆管家选出）〕
{旧案}

〔当前客户首问〕
客户：{首问}""" + 硬约束

办理提示 = """{店规}

你是办理员。只依据下面记忆管家交给你的页与客户档案回复客户，最后一行固定写：【转人工】是 或 【转人工】否。

〔客户档案（分诊台）〕
{档案}

〔记忆页（只拿该拿的这页）〕
{记忆页}""" + 用页硬规则 + """

〔客户消息〕
客户：{消息}""" + 硬约束

审核提示 = """{店规}

你是审核员，查账不放行问题件。对照事实页审查办理员的草稿：有没有事实页撑不住的具体断言（日期/金额/订单状态/承诺）、有没有答非所问、语气是否合规。
输出一行 JSON（不要别的）：{{"放行": true 或 false, "问题": ["<每条一句话>"]}}

〔客户消息〕
客户：{消息}

〔事实页（记忆管家选出）〕
{事实页}

〔办理员草稿〕
{草稿}""" + 硬约束

def 钉集():
    """当前 pin 在身的条目（店规常钉；最近分诊的客户档案被 pin_latest 钉着——F 顺序班里
    那就是当前会话的档案，S0 交错班里可能是别的客户的）。"""
    s = {"店规"}
    if 最近会话 is not None:
        s.add(f"会话{最近会话}·档案")
    return s

def 选页(task_state, role, budget, 必带):
    def 渲染(b, 尾注=""):
        条 = [镜像[i].text for i in b.selected_ids if i in 镜像]
        return "\n".join(f"- {t}" for t in 条) + 尾注 or "（无）"
    b = 钥匙.select(task_state=task_state, target_role=role, budget=budget, required_ids=必带)
    if b.conflict:
        落({"令": "select冲突降级", "role": role, "冲突": b.conflict, "必带": 必带})
        # 交错班差异④：降级预算＝必带∪钉集 的尺寸（F 写 len(必带)；引擎 mandatory=必带∪pinned，
        # 交错班里钉着的可能是别家档案 ⟹ len(必带) 装不下）。意图不变：并列时管家只交必带件、零可选位。
        b = 钥匙.select(task_state=task_state, target_role=role,
                        budget=len(set(必带) | 钉集()), required_ids=必带)
        assert not b.conflict, f"必带降级仍冲突：{b.conflict}"
        return b, 渲染(b, "\n（打分并列，管家只交必带件）")
    return b, 渲染(b)

档案库 = {}        # 交错班差异③：F 的全局 档案现 只在「会话顺序到场」时成立；S0 按会话各存各的
最近会话 = None   # 交错班差异②：分诊必带0 的「上一位」＝最近接待过的客户（JDDC 顺序班的对应物）

def 分诊阶段(k, 首问):
    钥匙.acting_agent = 号["分诊"]
    rb = 钥匙.recall(首问, budget=3, target_role="分诊")
    必带0 = ["店规"] + ([f"会话{最近会话}·档案"] if 最近会话 is not None else [])
    sb, 旧案 = 选页(f"新客户首问：{首问}", "分诊", 20, 必带0)
    分诊出 = 调工人("分诊", 分诊提示.format(店规=店规, 旧案=旧案, 首问=首问))
    档案o = 抽JSON(分诊出["回复"]) or {}
    档案库[k] = str(档案o.get("档案") or 分诊出["回复"][:80])
    记([ContextItem(id=f"会话{k}·档案", text=f"会话{k} 客户档案：{档案库[k]}", source="当前客户档案",
                    created_at=新序(), tags=("档案", str(档案o.get("问题类型", ""))))], f"会话{k} 分诊建档")
    pinid = 钥匙.pin_latest("当前客户档案")
    return {"旧案选中": list(sb.selected_ids), "旧案召回": list(rb.recalled_ids), "pinid": pinid,
            "分诊": {"回复": 分诊出["回复"], "usage": 分诊出.get("usage"), "墙钟秒": 分诊出.get("墙钟秒")}}

def 收尾compact(k):
    必带c = ["店规", f"会话{k}·档案"]
    cb = 钥匙.compact(task_state=f"会话{k} 收尾、这位客户暂告一段落", target_role="系统", budget=24)
    if cb.conflict:
        落({"令": "compact冲突降级", "会话": k, "冲突": cb.conflict})
        cb = 钥匙.compact(task_state=f"会话{k} 收尾、这位客户暂告一段落", target_role="系统",
                          budget=len(set(必带c) | 钉集()), required_ids=必带c)   # 同差异④
        assert not cb.conflict, f"compact 必带降级仍冲突：{cb.conflict}"
    return cb

def 主循环():
    global 最近会话
    全点 = []
    已分诊 = set()
    会话末流序 = {p["会话"]: max(q["流序"] for q in 点表 if q["会话"] == p["会话"]) for p in 点表}
    for 点 in 点表:
        k = 点["会话"]
        消息 = 点["消息"]
        新会话 = k not in 已分诊
        if 新会话:
            已分诊.add(k)
            分诊账 = 分诊阶段(k, 消息)
            最近会话 = k
        else:
            分诊账 = None

        记([ContextItem(id=f"会话{k}·n{点['流序']}客", text=点["标记行"],
                        source=f"会话{k}·对话", created_at=新序(), tags=("当班", "客户"))],
           f"会话{k} 当班进池（点{点['流序']}）")
        档案k = 档案库.get(k)

        窗口 = 会话对话.get(f"会话{k}", [])[-窗宽:]
        上我方 = (我方.get(f"会话{k}", []) or [])[-1:]      # 上一轮本会话办理终稿
        必带办 = ["店规", f"会话{k}·档案", *窗口, *上我方]
        必带审 = ["店规", f"会话{k}·档案", *窗口]

        d1 = 钥匙.dump(to_agent=号["办理"])
        (钥匙dir / f"点{点['流序']:03d}-交接-办理.json").write_text(json.dumps(交接头(d1), ensure_ascii=False), encoding="utf-8")
        钥匙.acting_agent = 号["办理"]
        gb, 记忆页 = 选页(f"回复客户消息：{消息}（档案：{档案k}）", "办理", 办理预算, 必带办)
        办理出 = 调工人("办理", 办理提示.format(店规=店规, 档案=档案k, 记忆页=记忆页, 消息=消息))
        草稿 = 办理出["回复"]

        d2 = 钥匙.dump(to_agent=号["审核"])
        (钥匙dir / f"点{点['流序']:03d}-交接-审核.json").write_text(json.dumps(交接头(d2), ensure_ascii=False), encoding="utf-8")
        钥匙.acting_agent = 号["审核"]
        vb, 事实页 = 选页(f"审核草稿（消息：{消息}）", "审核", 审核预算, 必带审)
        审核出 = 调工人("审核", 审核提示.format(店规=店规, 消息=消息, 事实页=事实页, 草稿=草稿))
        审o = 抽JSON(审核出["回复"])
        # ⚠️ fail closed（2026-08-26 补丁 A，见文件头注）：审核结果读不干净就**不许放行**。
        #    只有「解析出 dict，且『放行』字段确实是布尔 True」这一条路才放行；
        #    解析失败／字段缺失／字段不是布尔（含字符串 "false"）一律退回并标人工复核。
        需人工 = False
        if not isinstance(审o, dict):
            放行, 问题 = False, ["审核回复无法解析为 JSON —— fail closed，按退回处理，需人工复核"]
            审核态 = "解析失败·按退回落账"
            需人工 = True
        elif not isinstance(审o.get("放行"), bool):
            放行, 问题 = False, [f"审核回复的「放行」字段不是布尔值（收到 {审o.get('放行')!r}）"
                                 " —— fail closed，按退回处理，需人工复核"]
            审核态 = "放行字段非布尔·按退回落账"
            需人工 = True
        else:
            放行 = 审o["放行"]; 问题 = list(审o.get("问题") or [])
            审核态 = "放行" if 放行 else "退回"

        终稿, 终态 = 草稿, "首稿放行" if 放行 else "首稿"
        if not 放行:
            钥匙.acting_agent = 号["办理"]
            重试提示 = 办理提示.format(店规=店规, 档案=档案k, 记忆页=记忆页, 消息=消息) + \
                "\n\n〔审核员退回意见〕\n" + "\n".join(f"- {p}" for p in 问题) + "\n请修正后重新回复。"
            重试出 = 调工人("办理", 重试提示)
            终稿, 终态 = 重试出["回复"], "重试稿（审核退回后）"

        # 终稿记为「我方」条目（下一点进办理必带）
        记([ContextItem(id=f"会话{k}·r{点['流序']}", text=f"我方客服回复：{终稿}",
                        source=f"会话{k}·我方", created_at=新序(), tags=("我方",))], f"会话{k} 我方终稿（点{点['流序']}）")

        行 = {"段": "点", "会话": k, "流序": 点["流序"], "班点": 点["班点"], "判定": 点["判定"], "陷类": 点["陷类"],
              "话题": 点["话题"], "探针": 点["探针"],
              "消息": 消息, "标记行": 点["标记行"], "参照W": 点["参照回复"], "档案": 档案k,
              "窗口": list(窗口), "上我方": list(上我方),
              "办理页": list(gb.selected_ids), "事实页": list(vb.selected_ids),
              "草稿": 草稿, "终稿": 终稿, "终态": 终态, "审核态": 审核态, "审核问题": 问题,
              "需人工复核": 需人工,
              "办理": {"usage": 办理出.get("usage"), "墙钟秒": 办理出.get("墙钟秒")},
              "审核": {"回复": 审核出["回复"], "usage": 审核出.get("usage"), "墙钟秒": 审核出.get("墙钟秒")}}
        if 分诊账: 行 |= 分诊账
        if not 放行: 行["办理重试"] = {"usage": 重试出.get("usage"), "墙钟秒": 重试出.get("墙钟秒")}
        落(行); 全点.append(行)

        print(f"点{点['流序']:03d} 会话{k}{'·陷' if 点['判定'] else ''} 窗{len(窗口)}{'·我' if 上我方 else ''} {终态} {终稿[:24].replace(chr(10), ' ')}")
        if SMOKE:
            print("SMOKE：首工作点已全链，班终退出")
            break

    # 差异②落地：交错班的收尾 compact 全部推迟到班终、按各会话末点顺序逐会话补跑——
    # 中段 compact 会把还会回来的客户的窗口条目挤出活动区（required-ids-not-active；
    # JDDC 会话一去不返所以安全，S0 客户会回来。DRY 第二跑咬住）。
    if not SMOKE:
        钥匙.acting_agent = 号["编排"]
        for k in sorted(会话末流序, key=lambda x: 会话末流序[x]):
            cb = 收尾compact(k)
            落({"令": "会话收尾", "会话": k, "挤出": len(cb.evicted_ids)})

    钥匙.acting_agent = 号["编排"]
    钥匙.acting_agent = 号["编排"]
    钥匙.save(钥匙dir / "班终-钥匙S0.json")
    落({"令": "班终", "点数": len(全点), "账行数": len(钥匙.dump()['ledger_events']),
        "registry": 钥匙.agent_registry.to_dict()})

if __name__ == "__main__":
    try:
        主循环()
    finally:
        账f.close()
