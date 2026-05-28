"""CrimecastZA structured pipeline logger."""

import json
import time
from datetime import datetime, timezone


class PipelineLogger:
    """Emits structured JSON log entries to stdout.

    Each entry contains: timestamp, level, step, recordsProcessed,
    recordsSkipped, elapsedMs, message.
    Elapsed time is measured from the moment the logger is constructed.
    """

    def __init__(self, step: str) -> None:
        self._step = step
        self._start_time = time.time()

    def log(
        self,
        level: str,
        message: str,
        records_processed: int = 0,
        records_skipped: int = 0,
    ) -> None:
        """Emit a structured JSON log entry to stdout."""
        elapsed_ms = (time.time() - self._start_time) * 1000
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "step": self._step,
            "recordsProcessed": records_processed,
            "recordsSkipped": records_skipped,
            "elapsedMs": elapsed_ms,
            "message": message,
        }
        print(json.dumps(entry))
