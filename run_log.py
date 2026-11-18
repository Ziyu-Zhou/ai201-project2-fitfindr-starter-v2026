"""One persistent JSONL record per agent run, shared by CLI and HTTP callers."""

import json
import threading

import config

_lock = threading.Lock()


def append(record):
    """Append a complete record or surface the write error to the caller."""
    path = config.RUN_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line)
