import tempfile
import unittest
from pathlib import Path

from tokenwise.store import Ledger


class LedgerTests(unittest.TestCase):
    def test_persistent_runs_without_prompt_data(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Ledger(Path(temp) / "runs.sqlite3")
            saved = ledger.add({"requests_per_day": 9}, {"savings_pct": 42})
            reloaded = Ledger(Path(temp) / "runs.sqlite3").recent()
            self.assertEqual(reloaded[0]["id"], saved)
            self.assertEqual(reloaded[0]["result"]["savings_pct"], 42)


if __name__ == "__main__":
    unittest.main()
