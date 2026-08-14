"""Safe, fixed dependency helpers used by H3 Studio setup UI.

These routes never accept arbitrary repository URLs. They only manage the known
Mamad8 PDD node and the current ComfyUI checkout that is already running H3
Studio. Core updates are fast-forward only and refuse dirty checkouts.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    if root:
        return Path(root).resolve()
    return Path(folder_paths.__file__).resolve().parent


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


def _runtime_capabilities() -> dict[str, Any]:
    ck = False
    chunked_vae = False
    v3 = False
    try:
        import comfy.ldm.modules.attention as attention
        ck = bool(getattr(attention, "COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE", False))
        if not ck:
            ck = attention.get_attention_function("comfy_kitchen_int8", None) is not None
    except Exception:
        pass
    try:
        from comfy.ldm.cosmos.vae import CausalContinuousVideoTokenizer
        chunked_vae = bool(getattr(CausalContinuousVideoTokenizer, "comfy_has_chunked_io", False))
    except Exception:
        # The exact class location can move; H3 Studio's normal VAE capability
        # detector remains the source of truth at execution time.
        pass
    try:
        import comfy_api.latest  # type: ignore[import-not-found]
        v3 = True
    except Exception:
        try:
            import comfy_api  # type: ignore[import-not-found]
            v3 = hasattr(comfy_api, "latest")
        except Exception:
            pass
    return {"comfy_kitchen_int8": ck, "chunked_h3_vae": chunked_vae, "v3_extension_api": v3}


def dependency_status() -> dict[str, Any]:
    root = _comfy_root()
    pdd = _pdd_path()
    version = ""
    try:
        import comfyui_version
        version = str(getattr(comfyui_version, "__version__", ""))
    except Exception:
        pass
    return {
        "comfyui": {
            "root": str(root),
            "version": version,
            "git": (root / ".git").exists(),
            "head": _git_head(root),
            "dirty": _git_dirty(root),
            **_runtime_capabilities(),
        },
        "pdd": {
            "installed": pdd.exists(),
            "git": (pdd / ".git").exists(),
            "head": _git_head(pdd),
            "path_name": PDD_DIRNAME,
        },
    }


def install_or_update_pdd() -> dict[str, Any]:
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


def update_comfyui_master() -> dict[str, Any]:
    root = _comfy_root()
    if not (root / ".git").exists():
        raise RuntimeError("This ComfyUI installation is not a Git checkout; use ComfyUI-Manager's core updater instead.")
    if _git_dirty(root):
        raise RuntimeError("ComfyUI has local changes; refusing to overwrite them. Commit/stash them before updating core.")

    fetch = _run(["git", "fetch", "origin", "master"], root, 240)
    if fetch.returncode != 0:
        raise RuntimeError(fetch.stdout.strip() or "ComfyUI git fetch failed")
    checkout = _run(["git", "checkout", "master"], root)
    if checkout.returncode != 0:
        raise RuntimeError(checkout.stdout.strip() or "Could not switch ComfyUI to master")
    merge = _run(["git", "merge", "--ff-only", "origin/master"], root)
    if merge.returncode != 0:
        raise RuntimeError(merge.stdout.strip() or "ComfyUI update is not a fast-forward")

    requirements = root / "requirements.txt"
    if requirements.is_file():
        pip = _run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], root, 900)
        if pip.returncode != 0:
            raise RuntimeError(pip.stdout.strip() or "ComfyUI requirements update failed")
    return {"ok": True, "action": "updated", "head": _git_head(root), "restart_required": True}


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
            payload = dependency_status()
            # Do not expose absolute paths to the browser.
            payload["comfyui"].pop("root", None)
            return web.json_response(payload, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @server.routes.post("/h3studio/dependencies/pdd/install")
    async def h3studio_install_pdd(_request):
        try:
            return web.json_response(install_or_update_pdd())
        except Exception as exc:
            LOGGER.exception("[H3 Studio] PDD dependency install failed")
            return web.json_response({"ok": False, "error": str(exc)}, status=500)

    @server.routes.post("/h3studio/dependencies/comfyui/update")
    async def h3studio_update_comfyui(_request):
        try:
            return web.json_response(update_comfyui_master())
        except Exception as exc:
            LOGGER.exception("[H3 Studio] ComfyUI update failed")
            return web.json_response({"ok": False, "error": str(exc)}, status=500)
