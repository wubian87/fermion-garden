from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


class HandoffExampleTests(unittest.TestCase):
    def test_clean_checkout_handoff_example_has_two_attributed_sides(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(root / "examples" / "handoff_demo.py")],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "agents": {"sender": "000000001", "receiver": "000000002"},
                "handoff": {
                    "from_agent": "000000001",
                    "to_agent": "000000002",
                    "timestamp_has_timezone": True,
                },
                "receiver_identity": {
                    "before_claim": None,
                    "after_claim": "000000002",
                },
                "context": {
                    "active_ids": ["issue", "trace", "review", "retired"],
                    "recoverable_ids": ["noise"],
                    "recalled_ids": ["retired"],
                },
                "audit_event_counts": {
                    "sender": 8,
                    "receiver": 3,
                    "unattributed": 0,
                },
                "registry_resolves_both": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
