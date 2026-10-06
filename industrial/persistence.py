"""Append-oriented local persistence for industrial runtime evidence."""
from datetime import datetime, timezone
import json
import sqlite3


class IndustrialPersistence:
    def __init__(self, path):
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS industrial_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
            "recorded_at TEXT NOT NULL, category TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self._connection.commit()

    @staticmethod
    def _json(value):
        return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))

    def append(self, category, payload, recorded_at=None):
        timestamp = recorded_at or datetime.now(timezone.utc)
        cursor = self._connection.execute(
            "INSERT INTO industrial_events(recorded_at, category, payload) VALUES (?, ?, ?)",
            (timestamp.isoformat(), str(category), self._json(payload)),
        )
        self._connection.commit()
        return cursor.lastrowid

    def records(self):
        rows = self._connection.execute(
            "SELECT sequence, recorded_at, category, payload FROM industrial_events ORDER BY sequence"
        ).fetchall()
        return tuple({"sequence": row[0], "recorded_at": row[1], "category": row[2], "payload": json.loads(row[3])} for row in rows)

    def close(self):
        self._connection.close()
