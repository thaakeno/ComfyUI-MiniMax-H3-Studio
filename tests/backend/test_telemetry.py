from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_PATH = REPO_ROOT / "telemetry" / "telemetry.py"


def _load_telemetry_module():
    spec = importlib.util.spec_from_file_location("h3studio_test_telemetry", TELEMETRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("telemetry/telemetry.py is required for telemetry implementation tests")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runtime_loader_function():
    runtime_path = REPO_ROOT / "h3studio" / "nodes" / "image_runtime.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    function_node = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_load_telemetry_recorder"
    )
    isolated = ast.Module(body=[function_node], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {"importlib": __import__("importlib"), "Path": Path, "Optional": Optional}
    exec(compile(isolated, str(runtime_path), "exec"), namespace)
    return namespace["_load_telemetry_recorder"]


telemetry = _load_telemetry_module()
ImmediateReporter = telemetry.ImmediateReporter


def test_default_goatcounter_endpoint_is_finalized() -> None:
    assert telemetry.DEFAULT_ENDPOINT == "https://h3-studio.goatcounter.com/count"
    parsed = urllib.parse.urlsplit(telemetry._goatcounter_hit_url(telemetry.DEFAULT_ENDPOINT))
    assert parsed.scheme == "https"
    assert parsed.netloc == "h3-studio.goatcounter.com"
    assert parsed.path == "/count"
    assert urllib.parse.parse_qs(parsed.query) == {"p": ["/generated"], "ns": ["1"]}


def test_goatcounter_sender_expands_count_into_paced_no_session_hits(monkeypatch) -> None:
    captured = []
    sleeps = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _size):
            return b""

    def open_request(request, timeout):
        captured.append((request, timeout))
        return Response()

    monkeypatch.setenv("H3STUDIO_TELEMETRY_ENDPOINT", "https://h3-studio.goatcounter.com/count")
    monkeypatch.setattr(telemetry.urllib.request, "urlopen", open_request)
    monkeypatch.setattr(telemetry.time, "sleep", sleeps.append)

    telemetry._post_count(3)

    assert len(captured) == 3
    for request, timeout in captured:
        parsed = urllib.parse.urlsplit(request.full_url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "h3-studio.goatcounter.com"
        assert parsed.path == "/count"
        assert urllib.parse.parse_qs(parsed.query) == {"p": ["/generated"], "ns": ["1"]}
        assert request.method == "POST"
        assert request.data == b""
        headers = dict(request.header_items())
        assert headers["User-agent"] == "H3-Studio/2 Counter"
        assert "Authorization" not in headers
        assert timeout == 2.5

    assert sleeps == [telemetry.REQUEST_INTERVAL_SECONDS] * 3


def test_goatcounter_sender_rejects_non_https_endpoint(monkeypatch) -> None:
    called = False

    def open_request(_request, _timeout):
        nonlocal called
        called = True
        raise AssertionError("network should not be called")

    monkeypatch.setenv("H3STUDIO_TELEMETRY_ENDPOINT", "http://example.test/count")
    monkeypatch.setattr(telemetry.urllib.request, "urlopen", open_request)
    telemetry._post_count(5)
    assert called is False


def test_immediate_reporter_dispatches_without_batch_wait() -> None:
    sent: list[int] = []
    delivered = threading.Event()

    def sender(count: int) -> None:
        sent.append(count)
        delivered.set()

    reporter = ImmediateReporter(sender=sender, enabled=lambda: True)
    reporter.record(3)
    assert delivered.wait(1)
    assert sent == [3]


def test_immediate_reporter_opt_out_drops_counts() -> None:
    sent: list[int] = []
    reporter = ImmediateReporter(sender=sent.append, enabled=lambda: False)
    reporter.record(5)
    assert sent == []


def test_immediate_reporter_network_failure_never_reaches_caller() -> None:
    delivered = threading.Event()

    def failing_sender(_count: int) -> None:
        delivered.set()
        raise OSError("offline")

    reporter = ImmediateReporter(sender=failing_sender, enabled=lambda: True)
    reporter.record()
    assert delivered.wait(1)


def test_cli_disable_creates_persistent_opt_out_and_verifies_state(monkeypatch, tmp_path, capsys) -> None:
    opt_out = tmp_path / ".h3studio-telemetry-disabled"
    monkeypatch.setattr(telemetry, "OPT_OUT_FILE", opt_out)
    monkeypatch.delenv("H3STUDIO_TELEMETRY", raising=False)

    assert telemetry._cli(["disable"]) == 0
    assert opt_out.is_file()
    assert telemetry.telemetry_enabled() is False
    assert capsys.readouterr().out.strip() == "H3 telemetry: DISABLED"


def test_script_disable_command_works_end_to_end() -> None:
    opt_out = REPO_ROOT / ".h3studio-telemetry-disabled"
    opt_out.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, str(TELEMETRY_PATH), "disable"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "H3 telemetry: DISABLED"
        assert opt_out.is_file()
    finally:
        opt_out.unlink(missing_ok=True)


def test_missing_telemetry_folder_resolves_to_noop() -> None:
    loader = _load_runtime_loader_function()
    assert loader(REPO_ROOT / "telemetry" / "definitely-missing.py") is None


def test_runtime_loader_finds_only_explicit_telemetry_file(tmp_path) -> None:
    loader = _load_runtime_loader_function()
    module_path = tmp_path / "telemetry.py"
    module_path.write_text(
        "def record_generation_success(count=1):\n    return count\n",
        encoding="utf-8",
    )
    recorder = loader(module_path)
    assert recorder is not None
    assert recorder(7) == 7


def test_all_telemetry_implementation_files_live_in_top_level_folder() -> None:
    assert TELEMETRY_PATH.is_file()
    assert (REPO_ROOT / "telemetry" / "migrate_legacy_counter.py").is_file()
    assert not (REPO_ROOT / "h3studio" / "telemetry.py").exists()
