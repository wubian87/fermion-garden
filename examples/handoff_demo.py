#!/usr/bin/env python3
"""Two identities hand one offline ctx-key state to each other.

This is deliberately not an AgentTeams adapter or a message bus.  The dump is
passed in memory so the example isolates the L14.1 contract: the sender names
both ends, load never impersonates the receiver, and later ledger events show
which registered identity performed them.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fermion_garden import ContextItem, CtxKey  # noqa: E402


def run_handoff_demo() -> dict[str, object]:
    sender = CtxKey()
    investigator = sender.agent_registry.register("investigator in this offline example")
    fixer = sender.agent_registry.register("fixer in this offline example")
    sender.acting_agent = investigator

    sender.record(
        [
            ContextItem(
                "issue",
                "Timezone boundary fails when an offset crosses midnight.",
                source="issue",
                created_at=1,
                pinned=True,
            ),
            ContextItem(
                "trace",
                "The timezone boundary stacktrace points to normalize_offset.",
                source="test",
                created_at=2,
            ),
            ContextItem(
                "retired",
                "Retired hypothesis: timezone sign reversal breaks midnight rollover.",
                source="history",
                created_at=3,
            ),
            ContextItem(
                "noise",
                "The CSV exporter uses a different delimiter on Windows.",
                source="history",
                created_at=4,
            ),
        ],
        reason="investigator assembled the repair context",
    )
    sender.compact(
        task_state="repair the timezone midnight boundary",
        target_role="fixer",
        budget=2,
        trace_id="handoff-compact",
    )

    handed_off = sender.dump(to_agent=fixer)
    receiver = CtxKey.load(handed_off)
    acting_before_claim = receiver.acting_agent

    # The dump says who should receive it, but load intentionally does not act as
    # that identity.  The receiver must make the identity claim at its own write
    # boundary before it can put its number on later ledger events.
    receiver.acting_agent = fixer
    receiver.record(
        [ContextItem("review", "Verifier reproduced a timezone sign reversal at midnight.")],
        reason="fixer recorded verifier feedback",
    )
    recalled = receiver.recall(
        "timezone sign reversal at midnight",
        budget=1,
        target_role="fixer",
        trace_id="handoff-recall",
    )

    counts = Counter(event.agent_ref for event in receiver.ledger.events)
    handoff = receiver.last_handoff
    assert handoff is not None
    return {
        "agents": {"sender": investigator, "receiver": fixer},
        "handoff": {
            "from_agent": handoff["from_agent"],
            "to_agent": handoff["to_agent"],
            "timestamp_has_timezone": datetime.fromisoformat(handoff["at"]).tzinfo is not None,
        },
        "receiver_identity": {
            "before_claim": acting_before_claim,
            "after_claim": receiver.acting_agent,
        },
        "context": {
            "active_ids": list(receiver.active_ids),
            "recoverable_ids": list(receiver.recoverable_ids),
            "recalled_ids": list(recalled.recalled_ids),
        },
        "audit_event_counts": {
            "sender": counts[investigator],
            "receiver": counts[fixer],
            "unattributed": counts[None],
        },
        "registry_resolves_both": set(receiver.agent_registry.agents) == {investigator, fixer},
    }


def main() -> None:
    print(json.dumps(run_handoff_demo(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
