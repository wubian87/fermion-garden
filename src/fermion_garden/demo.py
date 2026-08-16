"""Offline demo with deterministic choices and runtime audit timestamps."""

from __future__ import annotations

import json

from .engine import CtxKey
from .models import ContextItem


def run_demo() -> dict[str, object]:
    items = [
        ContextItem(
            id="issue",
            text="Timezone boundary fails when an offset crosses midnight.",
            source="issue",
            created_at=1,
            pinned=True,
        ),
        ContextItem(
            id="stacktrace",
            text="The timezone boundary stacktrace points to normalize_offset.",
            source="test",
            created_at=2,
        ),
        ContextItem(
            id="interface",
            text="The public interface must preserve ISO offset formatting.",
            source="spec",
            created_at=3,
        ),
        ContextItem(
            id="retired-hypothesis",
            text="Retired hypothesis: timezone sign reversal may break midnight rollover.",
            source="history",
            tags=("dead-end",),
            created_at=4,
        ),
        ContextItem(
            id="unrelated",
            text="The CSV exporter uses a different delimiter on Windows.",
            source="history",
            created_at=5,
        ),
    ]
    garden = CtxKey(items)
    selected = garden.select(
        task_state="repair the timezone midnight boundary",
        target_role="fixer",
        budget=2,
        trace_id="demo-select",
    )
    compacted = garden.compact(
        task_state="repair the timezone midnight boundary",
        target_role="fixer",
        budget=2,
        trace_id="demo-compact",
    )
    recalled = garden.recall(
        "verifier reports timezone sign reversal at midnight; revisit retired hypothesis",
        budget=1,
        target_role="investigator",
        trace_id="demo-recall",
    )
    return {
        "selected": selected.to_dict(),
        "compacted": compacted.to_dict(),
        "recalled": recalled.to_dict(),
        "snapshot": garden.snapshot(),
        "audit": [event.to_dict() for event in garden.ledger.events],
    }


def main() -> None:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
