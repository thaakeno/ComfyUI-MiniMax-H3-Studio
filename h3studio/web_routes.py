"""Small authenticated-through-ComfyUI web helpers for the Studio panel."""

from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path

_THUMBNAILS: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
_MAX_CACHE_ITEMS = 128


def _safe_image_path(storage_name: str):
    import folder_paths

    text = str(storage_name or "").strip()
    if not text or ".." in text.replace("\\", "/").split("/"):
        raise ValueError("Unsafe image path.")
    path = Path(folder_paths.get_annotated_filepath(text)).resolve()
    allowed = [
        Path(folder_paths.get_input_directory()).resolve(),
        Path(folder_paths.get_output_directory()).resolve(),
        Path(folder_paths.get_temp_directory()).resolve(),
    ]
    if not any(path == root or root in path.parents for root in allowed):
        raise ValueError("Image is outside ComfyUI media folders.")
    return path


def _thumbnail_bytes(path: Path, size: int) -> bytes:
    from PIL import Image, ImageOps

    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, size)
    cached = _THUMBNAILS.get(key)
    if cached is not None:
        _THUMBNAILS.move_to_end(key)
        return cached
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=72, method=4)
        payload = buffer.getvalue()
    _THUMBNAILS[key] = payload
    while len(_THUMBNAILS) > _MAX_CACHE_ITEMS:
        _THUMBNAILS.popitem(last=False)
    return payload


def _lora_catalog() -> list[dict[str, object]]:
    """Return installed LoRA names without exposing absolute server paths."""

    import folder_paths

    result: list[dict[str, object]] = []
    for name in sorted(folder_paths.get_filename_list("loras"), key=str.casefold):
        normalized = str(name).replace("\\", "/")
        size_bytes = 0
        try:
            path = folder_paths.get_full_path("loras", name)
            if path:
                size_bytes = Path(path).stat().st_size
        except OSError:
            pass
        result.append({"name": normalized, "size_bytes": int(size_bytes)})
    return result


def register_routes() -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:
        return
    server = getattr(PromptServer, "instance", None)
    if server is None or getattr(server, "_h3studio_routes_registered", False):
        return
    server._h3studio_routes_registered = True

    @server.routes.get("/h3studio/thumbnail")
    async def h3studio_thumbnail(request):
        try:
            path = _safe_image_path(request.rel_url.query.get("storage", ""))
            if not path.is_file():
                return web.Response(status=404)
            size = max(48, min(256, int(request.rel_url.query.get("size", "112"))))
            return web.Response(
                body=_thumbnail_bytes(path, size),
                content_type="image/webp",
                headers={"Cache-Control": "private, max-age=86400"},
            )
        except (OSError, ValueError):
            return web.Response(status=400)

    @server.routes.get("/h3studio/loras")
    async def h3studio_loras(_request):
        try:
            items = _lora_catalog()
            return web.json_response(
                {"items": items, "count": len(items)},
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            return web.json_response(
                {"items": [], "count": 0, "error": f"Could not enumerate ComfyUI LoRAs: {exc}"},
                status=500,
                headers={"Cache-Control": "no-store"},
            )
