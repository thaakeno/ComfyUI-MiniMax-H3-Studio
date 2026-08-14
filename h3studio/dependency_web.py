"""Safe fixed dependency helper for the optional Mamad8 PDD custom node."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)
PDD_REPO = "https://github.com/mamad8c/ComfyUI-MiniMaxH3-PDD-Mamad8.git"
PDD_DIRNAME = "ComfyUI-MiniMaxH3-PDD-Mamad8"


def _run(args: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _comfy_root() -> Path:
    import folder_paths

    root = getattr(folder_paths, "base_path", None)
    return Path(root).resolve() if root else Path(folder_paths.__file__).resolve().parent


def _pdd_path() -> Path:
    return _comfy_root() / "custom_nodes" / PDD_DIRNAME


def _git_head(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    result = _run(["git", "rev-parse", "HEAD"], path, 20)
    return result.stdout.strip().splitlines()[-1] if result.returncode == 0 and result.stdout.strip() else ""


def _git_dirty(path: Path) -> bool:
    if not (path / ".git").exists():
        return False
    result = _run(["git", "status", "--porcelain"], path, 30)
    return bool(result.stdout.strip()) if result.returncode == 0 else True


def dependency_status() -> dict[str, object]:
    pdd = _pdd_path()
    return {
        "pdd": {
            "installed": pdd.exists(),
            "git": (pdd / ".git").exists(),
            "head": _git_head(pdd),
            "path_name": PDD_DIRNAME,
        }
    }


def install_or_update_pdd() -> dict[str, object]:
    target = _pdd_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not (target / ".git").exists():
            raise RuntimeError(f"{PDD_DIRNAME} exists but is not a Git checkout; refusing to overwrite it.")
        if _git_dirty(target):
            raise RuntimeError("PDD custom node has local changes; refusing to overwrite them. Commit/stash them or update manually.")
        fetch = _run(["git", "fetch", "origin", "main"], target)
        if fetch.returncode != 0:
            raise RuntimeError(fetch.stdout.strip() or "PDD git fetch failed")
        checkout = _run(["git", "checkout", "main"], target)
        if checkout.returncode != 0:
            raise RuntimeError(checkout.stdout.strip() or "Could not switch PDD custom node to main")
        merge = _run(["git", "merge", "--ff-only", "origin/main"], target)
        if merge.returncode != 0:
            raise RuntimeError(merge.stdout.strip() or "PDD update is not a fast-forward")
        action = "updated"
    else:
        clone = _run(["git", "clone", "--filter=blob:none", "--branch", "main", PDD_REPO, str(target)], target.parent)
        if clone.returncode != 0:
            raise RuntimeError(clone.stdout.strip() or "PDD git clone failed")
        action = "installed"
    return {"ok": True, "action": action, "head": _git_head(target), "restart_required": True}


def register_dependency_routes() -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None or getattr(server, "_h3studio_dependency_routes_registered", False):
        return
    server._h3studio_dependency_routes_registered = True

    @server.routes.get("/h3studio/dependencies/status")
    async def h3studio_dependency_status(_request):
        try:
            return web.json_response(dependency_status(), headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @server.routes.post("/h3studio/dependencies/pdd/install")
    async def h3studio_install_pdd(_request):
        try:
            return web.json_response(install_or_update_pdd())
        except Exception as exc:
            LOGGER.exception("[H3 Studio] PDD dependency install failed")
            return web.json_response({"ok": False, "error": str(exc)}, status=500)
