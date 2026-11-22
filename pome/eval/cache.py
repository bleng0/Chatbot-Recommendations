"""Response cache keyed by (config_id, prompt_sha256, run_idx) (CONSTRAINTS B).

Append-only JSONL, loaded into memory on open. A cached response is replayed at $0;
raw text is stored (not the parsed label) so parser fixes apply on replay.
"""
import json
import threading
from pathlib import Path
from typing import Any


class ResponseCache:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[tuple[str, str, int], dict[str, Any]] = {}
        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._data[(row["config_id"], row["prompt_sha256"], row["run_idx"])] = row["value"]

    def get(self, config_id: str, prompt_sha256: str, run_idx: int) -> dict[str, Any] | None:
        with self._lock:
            return self._data.get((config_id, prompt_sha256, run_idx))

    def put(self, config_id: str, prompt_sha256: str, run_idx: int, value: dict[str, Any]) -> None:
        row = {"config_id": config_id, "prompt_sha256": prompt_sha256, "run_idx": run_idx,
               "value": value}
        with self._lock:
            self._data[(config_id, prompt_sha256, run_idx)] = value
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
