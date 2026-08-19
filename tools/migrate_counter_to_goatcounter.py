"""One-time migration of the legacy H3 Studio image total to GoatCounter.

The GoatCounter API token is read only from GOATCOUNTER_API_TOKEN and is never
written to the repository. The script is dry-run by default; pass --apply to
actually seed the new counter.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request

LEGACY_COUNT_URL = "https://h3-studio-counter.h3-studio-counter.workers.dev/v1/count"
PATH = "/generated"
MAX_HITS_PER_REQUEST = 500


def _https_json(url: str, *, request: urllib.request.Request | None = None) -> dict:
    req = request or urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=15) as response:  # noqa: S310 - HTTPS URLs validated by caller
        return json.loads(response.read().decode("utf-8"))


def legacy_total(url: str = LEGACY_COUNT_URL) -> int:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("legacy counter URL must use HTTPS")
    separator = "&" if parsed.query else "?"
    data = _https_json(f"{url}{separator}ts={time.time_ns()}")
    total = data.get("reported_images_generated")
    if not isinstance(total, int) or total < 0:
        raise RuntimeError("legacy counter returned an invalid total")
    return total


def seed_batch(code: str, token: str, count: int) -> None:
    endpoint = f"https://{code}.goatcounter.com/api/v0/count"
    payload = json.dumps(
        {
            "no_sessions": True,
            "hits": [{"path": PATH} for _ in range(count)],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "H3-Studio-Counter-Migration/1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed GoatCounter HTTPS host
        if response.status != 202:
            raise RuntimeError(f"GoatCounter returned HTTP {response.status}")
        response.read(64)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate the H3 image total to hosted GoatCounter")
    parser.add_argument("--code", required=True, help="GoatCounter account code, e.g. h3studio")
    parser.add_argument("--count", type=int, help="Override the legacy total instead of fetching it")
    parser.add_argument("--apply", action="store_true", help="Actually write the historical hits")
    args = parser.parse_args()

    code = args.code.strip().lower()
    if not code or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in code):
        raise SystemExit("invalid GoatCounter account code")

    total = args.count if args.count is not None else legacy_total()
    if total < 0:
        raise SystemExit("count must be >= 0")

    batches = (total + MAX_HITS_PER_REQUEST - 1) // MAX_HITS_PER_REQUEST
    print(f"Legacy H3 Studio total: {total:,}")
    print(f"Target: https://{code}.goatcounter.com ({PATH})")
    print(f"Migration requests: {batches} (max {MAX_HITS_PER_REQUEST} hits each)")

    if not args.apply:
        print("DRY RUN only. Re-run with --apply after confirming the new GoatCounter site is empty.")
        return 0

    token = os.getenv("GOATCOUNTER_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("GOATCOUNTER_API_TOKEN is not set")

    remaining = total
    migrated = 0
    while remaining:
        size = min(remaining, MAX_HITS_PER_REQUEST)
        seed_batch(code, token, size)
        migrated += size
        remaining -= size
        print(f"Migrated {migrated:,}/{total:,}")
        if remaining:
            time.sleep(0.35)

    print("Migration accepted by GoatCounter. Allow a few seconds for background persistence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
