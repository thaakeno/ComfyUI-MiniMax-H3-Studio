"""Image inputs shared by linked media and Director-integrated uploads."""

from __future__ import annotations

from typing import Any

from .constants import MAX_REFERENCE_IMAGES
from .references import clean_filename, clean_storage_name


def load_uploaded_image(storage_name: str, ordinal: int) -> Any:
    """Load one Director-uploaded image through ComfyUI's canonical loader."""

    safe_name = clean_storage_name(storage_name)
    if not safe_name:
        raise ValueError(f"Image {ordinal} has an invalid ComfyUI input filename. Remove it and upload it again.")
    try:
        from nodes import LoadImage

        image, _mask = LoadImage().load_image(safe_name)
    except Exception as exc:
        raise ValueError(
            f"Image {ordinal} could not be loaded from ComfyUI input storage: {safe_name!r}. "
            "Remove the card and upload the image again."
        ) from exc
    return image


def collect_images(kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], tuple[str, ...], tuple[str | None, ...]]:
    """Collect ordered tensors from links or integrated ComfyUI uploads."""

    images: list[Any] = []
    filenames: list[str] = []
    storage_names: list[str | None] = []
    direct = kwargs.get("media")
    if direct is not None:
        images.append(direct)
        filenames.append(str(kwargs.get("media_filename") or "image_1.png"))
        storage_names.append(None)
    for index in range(1, MAX_REFERENCE_IMAGES + 1):
        image = kwargs.get(f"media_{index}")
        raw_storage_name = str(kwargs.get(f"media_filename_{index}") or "").strip()
        storage_name = clean_storage_name(raw_storage_name)
        if image is None and raw_storage_name and not storage_name:
            raise ValueError(
                f"Image {len(images) + 1} has an invalid ComfyUI input filename. Remove it and upload it again."
            )
        if image is None and not storage_name:
            continue
        media_type = str(kwargs.get(f"media_type_{index}") or "image").strip().lower()
        if media_type not in {"", "image"}:
            raise ValueError("H3 Studio image workflows accept image references only; remove video/audio media links.")
        is_uploaded = image is None
        if is_uploaded:
            image = load_uploaded_image(storage_name, len(images) + 1)
        images.append(image)
        filenames.append(clean_filename(storage_name) or f"image_{len(images)}.png")
        storage_names.append(storage_name if is_uploaded else None)
    return (
        tuple(images[:MAX_REFERENCE_IMAGES]),
        tuple(filenames[:MAX_REFERENCE_IMAGES]),
        tuple(storage_names[:MAX_REFERENCE_IMAGES]),
    )
