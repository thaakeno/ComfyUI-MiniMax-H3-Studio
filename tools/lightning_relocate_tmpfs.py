#!/usr/bin/env python3
"""Relocate real H3 model files out of /dev/shm without changing model paths.

Lightning launchers may register ``/dev/shm/h3-models`` before persistent model
folders. On a 32 GiB host, keeping 10-15+ GiB safetensors physically in tmpfs
leaves too little RAM for ComfyUI's staged DynamicVRAM weights. This tool copies
regular files to persistent storage, verifies their size, then replaces each
source file with a symlink to the persistent copy.

Dry-run is the default. Pass ``--apply`` to make changes.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

GIB = 1024**3
DEFAULT_SOURCE = Path("/dev/shm/h3-models")
DEFAULT_DESTINATION = Path("/teamspace/studios/this_studio/h3-models-persistent")


def regular_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    values = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        values.append(path)
    return sorted(values)


def human(value: int) -> str:
    return f"{value / GIB:.2f} GiB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--apply", action="store_true", help="Copy, verify, and replace tmpfs files with symlinks.")
    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()
    files = regular_files(source)
    total = sum(path.stat().st_size for path in files)

    print(f"source:      {source}")
    print(f"destination: {destination}")
    print(f"real files:  {len(files)}")
    print(f"tmpfs bytes: {human(total)}")
    if not files:
        print("Nothing to relocate. Existing symlinks are already disk-backed.")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    needed = 0
    for path in files:
        relative = path.relative_to(source)
        target = destination / relative
        if not target.is_file() or target.stat().st_size != path.stat().st_size:
            needed += path.stat().st_size

    free = shutil.disk_usage(destination).free
    print(f"new disk copy required: {human(needed)}")
    print(f"persistent free space:  {human(free)}")
    if needed and free < needed + 2 * GIB:
        raise SystemExit(
            f"Refusing migration: need {human(needed + 2 * GIB)} free including safety margin, have {human(free)}."
        )

    for source_file in files:
        relative = source_file.relative_to(source)
        target = destination / relative
        print(f"{'APPLY' if args.apply else 'DRY '} {relative} ({human(source_file.stat().st_size)})")
        if not args.apply:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        source_size = source_file.stat().st_size
        if not target.is_file() or target.stat().st_size != source_size:
            temporary = target.with_name(target.name + ".h3studio-copying")
            if temporary.exists():
                temporary.unlink()
            shutil.copy2(source_file, temporary)
            if temporary.stat().st_size != source_size:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"Size verification failed for {relative}")
            os.replace(temporary, target)

        # Only free tmpfs after the persistent file has been verified.
        if target.stat().st_size != source_size:
            raise RuntimeError(f"Persistent verification failed for {relative}")
        source_file.unlink()
        source_file.symlink_to(target)

    if args.apply:
        remaining = sum(path.stat().st_size for path in regular_files(source))
        print(f"Done. Real tmpfs model bytes remaining: {human(remaining)}")
        print("The launcher can keep using /dev/shm/h3-models; those paths now resolve to persistent storage.")
    else:
        print("Dry run only. Re-run with --apply after reviewing the list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
