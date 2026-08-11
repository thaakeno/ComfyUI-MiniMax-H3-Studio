"""Privacy-minimal, non-blocking aggregate generation counter."""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

DEFAULT_ENDPOINT = "https://h3-studio-counter.thaakeno.workers.dev/v1/report"
OPT_OUT_FILE = Path(__file__).resolve().parents[1] / ".h3studio-telemetry-disabled"


def telemetry_enabled() -> bool:
    value = os.getenv("H3STUDIO_TELEMETRY", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"} and not OPT_OUT_FILE.exists()


def _post_count(count: int) -> None:
    endpoint = os.getenv("H3STUDIO_TELEMETRY_ENDPOINT", DEFAULT_ENDPOINT).strip()
    if not endpoint.startswith("https://"):
        return
    payload = json.dumps({"count": int(count), "schema": 1}, separators=(",", ":")).encode("ascii")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "H3-Studio-Aggregate-Counter/1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2.5) as response:  # noqa: S310 - fixed HTTPS endpoint
        response.read(64)


class AggregateReporter:
    """Batch anonymous integer increments without delaying image execution."""

    def __init__(
        self,
        *,
        batch_size: int = 10,
        flush_seconds: float = 300.0,
        sender: Callable[[int], None] = _post_count,
        enabled: Callable[[], bool] = telemetry_enabled,
    ) -> None:
        self.batch_size = max(1, int(batch_size))
        self.flush_seconds = max(1.0, float(flush_seconds))
        self.sender = sender
        self.enabled = enabled
        self._pending = 0
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def record(self, count: int = 1) -> None:
        value = max(0, int(count))
        if not value or not self.enabled():
            return
        flush = 0
        with self._lock:
            self._pending = min(10_000, self._pending + value)
            if self._pending >= self.batch_size:
                flush = self._drain_locked()
            elif self._timer is None:
                self._timer = threading.Timer(self.flush_seconds, self.flush)
                self._timer.daemon = True
                self._timer.start()
        if flush:
            self._send_async(flush)

    def _drain_locked(self) -> int:
        count, self._pending = self._pending, 0
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        return count

    def flush(self) -> None:
        with self._lock:
            count = self._drain_locked()
        if count:
            self._send_async(count)

    def _send_async(self, count: int) -> None:
        def send() -> None:
            with suppress(Exception):
                self.sender(count)

        threading.Thread(target=send, name="h3studio-aggregate-counter", daemon=True).start()


_REPORTER = AggregateReporter()


def record_generation_success(count: int = 1) -> None:
    """Record only a successful output count; no generation data is accepted."""

    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    _REPORTER.record(count)
