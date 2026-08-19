"""Compatibility bridge for the optional H3 Studio telemetry folder.

The network-facing implementation lives entirely in ``../telemetry/client.py``.
If the top-level ``telemetry`` directory is removed, H3 Studio treats telemetry
as disabled and all generation paths keep working normally.
"""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

_CLIENT_PATH = Path(__file__).resolve().parents[1] / "telemetry" / "client.py"


def _load_client(path: Path = _CLIENT_PATH) -> ModuleType | None:
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("h3studio_optional_telemetry_client", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        # Telemetry must never prevent H3 Studio from loading or generating.
        return None


_CLIENT = _load_client()


def telemetry_enabled() -> bool:
    if _CLIENT is None:
        return False
    return bool(_CLIENT.telemetry_enabled())


def record_generation_success(count: int = 1) -> None:
    if _CLIENT is None:
        return
    _CLIENT.record_generation_success(count)


def _cli(argv: Sequence[str] | None = None) -> int:
    if _CLIENT is not None:
        return int(_CLIENT._cli(argv))

    parser = argparse.ArgumentParser(prog="python -m h3studio.telemetry")
    parser.add_argument("command", choices=("disable", "enable", "status"))
    parser.parse_args(argv)
    print("H3 telemetry: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
