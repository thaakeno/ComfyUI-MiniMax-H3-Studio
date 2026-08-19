"""Privacy-minimal, non-blocking aggregate generation counter."""

from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path

# Filled with the hosted GoatCounter /count URL at cutover time. Keeping this
# empty on the migration branch makes the branch fail closed rather than send
# telemetry to the legacy Cloudflare endpoint.
DEFAULT_ENDPOINT = ""
GOATCOUNTER_PATH = "/generated"
REQUEST_INTERVAL_SECONDS = 0.40
OPT_OUT_FILE = Path(__file__).resolve().parents[1] / ".h3studio-telemetry-disabled"
_SEND_LOCK = threading.Lock()


def telemetry_enabled() -> bool:
    value = os.getenv("H3STUDIO_TELEMETRY", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"} and not OPT_OUT_FILE.exists()


def _goatcounter_hit_url(endpoint: str) -> str:
    """Build a GoatCounter request containing only the counter path + no-session flag."""

    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    query = urllib.parse.urlencode({"p": GOATCOUNTER_PATH, "ns": "1"})
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/count", query, ""))


def _send_goatcounter_hit(url: str) -> None:
    request = urllib.request.Request(
        url,
        data=b"",
        headers={"User-Agent": "H3-Studio-Counter/2"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=2.5) as response:  # noqa: S310 - HTTPS endpoint only
            response.read(64)
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise
        retry_after = exc.headers.get("Retry-After", "1") if exc.headers else "1"
        try:
            delay = float(retry_after)
        except ValueError:
            delay = 1.0
        time.sleep(min(5.0, max(0.5, delay)))
        with urllib.request.urlopen(request, timeout=2.5) as response:  # noqa: S310 - HTTPS endpoint only
            response.read(64)


def _post_count(count: int) -> None:
    """Expand a local aggregate into anonymous no-session GoatCounter hits."""

    endpoint = os.getenv("H3STUDIO_TELEMETRY_ENDPOINT", DEFAULT_ENDPOINT).strip()
    url = _goatcounter_hit_url(endpoint)
    value = max(0, int(count))
    if not url or not value:
        return

    # GoatCounter's public /count endpoint is rate-limited per source. Serialize
    # all background batches and stay comfortably below its 4 requests/s default.
    with _SEND_LOCK:
        for index in range(value):
            _send_goatcounter_hit(url)
            if index + 1 < value:
                time.sleep(REQUEST_INTERVAL_SECONDS)


class AggregateReporter:
    """Batch anonymous integer increments without delaying image execution."""

    def __init__(
        self,
        *,
        batch_size: int = 10,
        flush_seconds: float = 60.0,
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


def _cli(argv: Sequence[str] | None = None) -> int:
    """Manage the persistent per-install telemetry opt-out."""

    import argparse

    parser = argparse.ArgumentParser(prog="python -m h3studio.telemetry")
    parser.add_argument("command", choices=("disable", "enable", "status"))
    command = parser.parse_args(argv).command

    if command == "disable":
        OPT_OUT_FILE.touch(exist_ok=True)
        if not telemetry_enabled():
            print("H3 telemetry: DISABLED")
            return 0
        return 1

    if command == "enable":
        OPT_OUT_FILE.unlink(missing_ok=True)

    enabled = telemetry_enabled()
    print(f"H3 telemetry: {'ENABLED' if enabled else 'DISABLED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
