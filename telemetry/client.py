"""Optional, privacy-minimal generated-image counter client.

This file contains the entire network-facing telemetry implementation. H3 Studio
loads it through a small compatibility bridge; deleting the top-level
``telemetry`` directory therefore disables telemetry without breaking the node.
"""

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

DEFAULT_ENDPOINT = "https://h3-studio.goatcounter.com/count"
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
        headers={"User-Agent": "H3-Studio/2 Counter"},
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
    """Send successful outputs to GoatCounter immediately, paced below its public limit."""

    endpoint = os.getenv("H3STUDIO_TELEMETRY_ENDPOINT", DEFAULT_ENDPOINT).strip()
    url = _goatcounter_hit_url(endpoint)
    value = max(0, int(count))
    if not url or not value:
        return

    # All reporting is background-only. Keep the lock across the pacing delay so
    # independent generations cannot burst above GoatCounter's public 4 req/s limit.
    with _SEND_LOCK:
        for _ in range(value):
            _send_goatcounter_hit(url)
            time.sleep(REQUEST_INTERVAL_SECONDS)


class ImmediateReporter:
    """Dispatch successful output counts immediately without delaying generation."""

    def __init__(
        self,
        *,
        sender: Callable[[int], None] = _post_count,
        enabled: Callable[[], bool] = telemetry_enabled,
    ) -> None:
        self.sender = sender
        self.enabled = enabled

    def record(self, count: int = 1) -> None:
        value = max(0, int(count))
        if not value or not self.enabled():
            return

        def send() -> None:
            with suppress(Exception):
                self.sender(value)

        threading.Thread(target=send, name="h3studio-counter", daemon=True).start()


_REPORTER = ImmediateReporter()


def record_generation_success(count: int = 1) -> None:
    """Immediately queue successful outputs for anonymous background counting."""

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
