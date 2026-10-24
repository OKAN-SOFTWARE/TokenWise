"""Local-only, parameterized SQLite evidence ledger. Prompts are never stored."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY, created_utc TEXT NOT NULL,
                scenario_json TEXT NOT NULL, result_json TEXT NOT NULL
            )""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def add(self, scenario: dict, result: dict) -> str:
        identifier = str(uuid4())
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            db.execute("INSERT INTO simulations VALUES (?, ?, ?, ?)",
                       (identifier, created, json.dumps(scenario), json.dumps(result)))
            db.execute("""DELETE FROM simulations WHERE id NOT IN
                          (SELECT id FROM simulations ORDER BY created_utc DESC, rowid DESC LIMIT 250)""")
        return identifier

    def recent(self, count: int = 12) -> list[dict]:
        count = min(max(int(count), 1), 50)
        with self._connect() as db:
            rows = db.execute("""SELECT id, created_utc, scenario_json, result_json
                                 FROM simulations ORDER BY created_utc DESC, rowid DESC LIMIT ?""",
                              (count,)).fetchall()
        return [{"id": row[0], "created_utc": row[1], "scenario": json.loads(row[2]),
                 "result": json.loads(row[3])} for row in rows]
