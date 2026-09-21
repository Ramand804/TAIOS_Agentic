from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any

class JsonlLogger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: Any):
        payload = record.to_dict() if hasattr(record, "to_dict") else record
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def write_all(self, records):
        """Replace a complete run log atomically; retain write() append semantics."""
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             delete=False) as stream:
                temporary = Path(stream.name)
                for record in records:
                    payload = record.to_dict() if hasattr(record, "to_dict") else record
                    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
