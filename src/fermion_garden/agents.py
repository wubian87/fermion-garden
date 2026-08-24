"""L14.1 存在身份注册处（agent registry）——给「干活的那个存在」发身份。

设计正身：母库 220 注 结果.md（园主 2026-08-24 批「要开注」、同日深夜批「落」；
9 位定宽亦园主形状：8 腕＋1 脑＝9，单数满）。三条设计红线随码走：

1. ⛔ 单个号上不发语义：角色／权限／型号不编进号——谁是脑袋是角色的事，
   戴显式标签（星世界「两顶帽子」），号只纪念身体形状（号宽 9），不指认个体。
2. 顺序发号、不预留特号：谁先登记谁拿 000000001，人（含园主）与 AI 同一队列。
3. 满编不是封顶：登记到第 9 个存在时命名意义上的八爪鱼满编（1＋8），
   第 10 个照拿 000000010——身体形状是命名典故，不是容量上限。

与 L11.2 规则身份（rule_identities）分层：那边给判据／口径发身份，这边给存在发；
库本体钥匙级一份（同 l112run 分叉#8 形状），账行只带 agent_ref 引用。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

AGENT_REF_PATTERN = re.compile(r"^[0-9]{9}$")


def is_agent_ref(value: object) -> bool:
    """9 位定宽十进制＝存在号；其他长度是事件层各形（trace_id 等），不是存在号。"""
    return isinstance(value, str) and AGENT_REF_PATTERN.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class AgentRecord:
    number: str
    registered_at: str
    note: str

    def to_dict(self) -> dict[str, str]:
        return {
            "number": self.number,
            "registered_at": self.registered_at,
            "note": self.note,
        }


class AgentRegistry:
    """存在身份注册处。号由 register() 唯一发放口产生（⛔ 不接受外部造号入册）。"""

    def __init__(self) -> None:
        self._agents: dict[str, AgentRecord] = {}
        self._next = 1

    def register(self, note: str = "") -> str:
        number = f"{self._next:09d}"
        self._next += 1
        self._agents[number] = AgentRecord(
            number, datetime.now(timezone.utc).isoformat(), note
        )
        return number

    @property
    def agents(self) -> dict[str, AgentRecord]:
        return dict(self._agents)

    def to_dict(self) -> dict[str, object]:
        return {
            "next": self._next,
            "agents": [record.to_dict() for record in self._agents.values()],
        }

    @classmethod
    def from_dict(cls, dumped: dict[str, object]) -> "AgentRegistry":
        restored = cls()
        restored._next = int(dumped["next"])
        for row in dumped["agents"]:
            record = AgentRecord(
                str(row["number"]), str(row["registered_at"]), str(row["note"])
            )
            if not is_agent_ref(record.number):
                raise ValueError(
                    f"agent number {record.number!r} is not 9-digit fixed width; refusing to load"
                )
            if record.number in restored._agents:
                raise ValueError(f"duplicate agent number {record.number!r}; refusing to load")
            restored._agents[record.number] = record
        return restored
