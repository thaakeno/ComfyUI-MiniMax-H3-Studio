"""Migrate the legacy H3 Studio image total to GoatCounter.

The GoatCounter API token is read only from GOATCOUNTER_API_TOKEN and is never
written to the repository. The script is dry-run by default; pass --apply to
actually seed GoatCounter.
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
API_BATCH_INTERVAL_SECONDS = 2.1


def _https_json(url: str, *, request: urllib.request.Request | None = None) -> dict:
    req = request or urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "H3-Studio-Counter-Migration/1",
        },
    )
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
            "filter": [],
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
    parser.add_argument("--code", required=True, help="GoatCounter account code, e.g. h3-studio")
    parser.add_argument("--count", type=int, help="Import exactly this many historical hits")
    parser.add_argument(
        "--delta-from",
        type=int,
        help="Fetch the current legacy total and import only the increase since this saved checkpoint",
    )
    parser.add_argument("--apply", action="store_true", help="Actually write the historical hits")
    args = parser.parse_args()

    code = args.code.strip().lower()
    if not code or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in code):
        raise SystemExit("invalid GoatCounter account code")
    if args.count is not None and args.delta_from is not None:
        raise SystemExit("use either --count or --delta-from, not both")
    if args.count is not None and args.count < 0:
        raise SystemExit("count must be >= 0")
    if args.delta_from is not None and args.delta_from < 0:
        raise SystemExit("delta checkpoint must be >= 0")

    next_checkpoint: int | None = None
    if args.delta_from is not None:
        current_legacy = legacy_total()
        if current_legacy < args.delta_from:
            raise SystemExit(
                f"legacy total {current_legacy:,} is below checkpoint {args.delta_from:,}; refusing to import"
            )
        total = current_legacy - args.delta_from
        next_checkpoint = current_legacy
        print(f"Legacy checkpoint: {args.delta_from:,}")
        print(f"Legacy H3 Studio now: {current_legacy:,}")
        print(f"Delta to import: {total:,}")
    else:
        total = args.count if args.count is not None else legacy_total()
        print(f"Legacy H3 Studio total: {total:,}")

    batches = (total + MAX_HITS_PER_REQUEST - 1) // MAX_HITS_PER_REQUEST
    print(f"Target: https://{code}.goatcounter.com ({PATH})")
    print(f"Migration requests: {batches} (max {MAX_HITS_PER_REQUEST} hits each)")

    if total == 0:
        print("Nothing to import.")
        if next_checkpoint is not None:
            print(f"Next legacy checkpoint: {next_checkpoint:,}")
        return 0

    if not args.apply:
        if args.delta_from is not None:
            print("DRY RUN only. Re-run with --apply to import this legacy delta.")
        else:
            print("DRY RUN only. Re-run with --apply after confirming the target count is correct.")
        if next_checkpoint is not None:
            print(f"Next legacy checkpoint after a successful apply: {next_checkpoint:,}")
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
            # GoatCounter's /api/v0/count has its own 60 requests / 120 seconds
            # limit; this keeps even larger migrations inside that default.
            time.sleep(API_BATCH_INTERVAL_SECONDS)

    print("Migration accepted by GoatCounter. Allow a few seconds for background persistence.")
    if next_checkpoint is not None:
        print(f"Next legacy checkpoint: {next_checkpoint:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
