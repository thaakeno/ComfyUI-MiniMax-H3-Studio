"""Optional ComfyUI-native Qwen-VL prompt enhancement.

This module is intentionally independent from the Qwen3-VL checkpoint loaded by
ComfyUI's ``CLIPLoader(type=minimax)``. That checkpoint produces H3 conditioning;
it is not assumed to expose an autoregressive ``generate`` interface.

No model is downloaded automatically. A local Transformers model directory must
be selected explicitly, and the adapter unloads after each call unless requested
otherwise.
"""

from __future__ import annotations

import gc
import json
import threading
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import OptionalDependencyError, PromptFormatError
from ..references import ReferenceImage
from ..state import StudioState
from .compiler import CompileResult, PromptCompiler
from .templates import DETAIL_GUIDANCE, IMAGE_REWRITE_SYSTEM_INSTRUCTION


@dataclass(frozen=True, slots=True)
class VLMRequest:
    model_path: str
    prompt: str
    references: tuple[ReferenceImage, ...]
    images: tuple[Any, ...]
    system_instruction: str = IMAGE_REWRITE_SYSTEM_INSTRUCTION
    device: str = "auto"
    quantization: str = "auto"
    max_tokens: int = 1800
    temperature: float = 0.2
    top_p: float = 0.9
    seed: int = 0
    keep_loaded: bool = False
    local_files_only: bool = True


@dataclass(frozen=True, slots=True)
class VLMResult:
    text: str
    model_path: str
    device: str
    quantization: str
    input_images: int
    generation_kwargs: dict[str, Any]

    def summary(self) -> str:
        return (
            f"VLM={self.model_path} · device={self.device} · quantization={self.quantization} · "
            f"images={self.input_images} · max_tokens={self.generation_kwargs.get('max_new_tokens')}"
        )


class _ModelHandle:
    def __init__(self, signature: tuple[str, str, str], model: Any, processor: Any, device: str) -> None:
        self.signature = signature
        self.model = model
        self.processor = processor
        self.device = device

    def clear(self) -> None:
        model = self.model
        self.model = None
        self.processor = None
        if model is not None:
            with suppress(Exception):
                model.to("cpu")
        del model
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass


class QwenVLAdapter:
    """Small, explicit Transformers adapter with one-process model caching."""

    _lock = threading.RLock()
    _handle: _ModelHandle | None = None

    @staticmethod
    def dependencies() -> tuple[Any, Any, Any]:
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor
        except ImportError as exc:
            raise OptionalDependencyError(
                "VLM enhancement requires Transformers, Accelerate and qwen-vl-utils.",
                hint='Install the optional dependencies with: pip install -e ".[vlm]"',
            ) from exc
        return torch, AutoModelForImageTextToText, AutoProcessor

    @staticmethod
    def validate_model_path(value: str, *, local_files_only: bool = True) -> str:
        model_path = str(value or "").strip()
        if not model_path:
            raise OptionalDependencyError(
                "No VLM analyzer model is selected.",
                hint="Choose a local Qwen3-VL Instruct model or use Compile Only.",
            )
        if local_files_only and not Path(model_path).expanduser().exists():
            raise OptionalDependencyError(
                f"VLM model path does not exist locally: {model_path}",
                hint="H3 Studio never downloads analyzer weights automatically.",
            )
        return str(Path(model_path).expanduser().resolve()) if Path(model_path).expanduser().exists() else model_path

    @staticmethod
    def resolve_device(requested: str, torch: Any) -> str:
        requested = str(requested or "auto").lower()
        if requested == "auto":
            if torch.cuda.is_available():
                return "cuda"
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise OptionalDependencyError(f"Requested VLM device {requested}, but CUDA is unavailable.")
        return requested

    @staticmethod
    def model_kwargs(quantization: str, device: str, torch: Any) -> dict[str, Any]:
        quantization = str(quantization or "auto").lower()
        kwargs: dict[str, Any] = {"low_cpu_mem_usage": True}
        if device.startswith("cuda"):
            kwargs["device_map"] = device
            kwargs["torch_dtype"] = torch.bfloat16
        elif device == "mps":
            kwargs["device_map"] = "mps"
            kwargs["torch_dtype"] = torch.float16
        else:
            kwargs["device_map"] = "cpu"
            kwargs["torch_dtype"] = torch.float32
        if quantization in {"4bit", "int4", "nf4"}:
            try:
                from transformers import BitsAndBytesConfig
            except ImportError as exc:
                raise OptionalDependencyError("4-bit VLM loading requires bitsandbytes.") from exc
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            kwargs.pop("torch_dtype", None)
        elif quantization in {"8bit", "int8"}:
            try:
                from transformers import BitsAndBytesConfig
            except ImportError as exc:
                raise OptionalDependencyError("8-bit VLM loading requires bitsandbytes.") from exc
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            kwargs.pop("torch_dtype", None)
        elif quantization not in {"auto", "none", "bf16", "fp16", "fp32"}:
            raise OptionalDependencyError(f"Unsupported VLM quantization mode: {quantization}")
        return kwargs

    @classmethod
    def _load(cls, request: VLMRequest) -> _ModelHandle:
        torch, model_class, processor_class = cls.dependencies()
        model_path = cls.validate_model_path(request.model_path, local_files_only=request.local_files_only)
        device = cls.resolve_device(request.device, torch)
        quantization = str(request.quantization or "auto").lower()
        signature = (model_path, device, quantization)
        with cls._lock:
            if cls._handle and cls._handle.signature == signature:
                return cls._handle
            cls.unload()
            kwargs = cls.model_kwargs(quantization, device, torch)
            kwargs["local_files_only"] = request.local_files_only
            processor = processor_class.from_pretrained(model_path, local_files_only=request.local_files_only)
            model = model_class.from_pretrained(model_path, **kwargs)
            model.eval()
            cls._handle = _ModelHandle(signature, model, processor, device)
            return cls._handle

    @classmethod
    def unload(cls) -> None:
        with cls._lock:
            handle, cls._handle = cls._handle, None
            if handle:
                handle.clear()

    @staticmethod
    def _to_pil(image: Any) -> Any:
        try:
            from PIL import Image
        except ImportError as exc:
            raise OptionalDependencyError("Pillow is required for VLM image analysis.") from exc
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        try:
            import numpy as np
            import torch
        except ImportError as exc:
            raise OptionalDependencyError("NumPy and PyTorch are required for ComfyUI image conversion.") from exc
        value = image
        if isinstance(value, torch.Tensor):
            value = value.detach().float().cpu()
            if value.ndim == 4:
                value = value[0]
            if value.ndim == 3 and value.shape[0] in {1, 3, 4} and value.shape[-1] not in {1, 3, 4}:
                value = value.movedim(0, -1)
            value = value.clamp(0, 1).mul(255).byte().numpy()
        elif not isinstance(value, np.ndarray):
            raise OptionalDependencyError(f"Unsupported VLM image value: {type(image).__name__}")
        if value.dtype != np.uint8:
            maximum = float(value.max()) if value.size else 1.0
            if maximum <= 1.0:
                value = value * 255.0
            value = value.clip(0, 255).astype(np.uint8)
        return Image.fromarray(value).convert("RGB")

    @staticmethod
    def _user_instruction(request: VLMRequest) -> str:
        reference_lines = []
        for reference in request.references:
            description = reference.description or "Analyze the visible reference directly."
            reference_lines.append(
                f"- @Image{reference.ordinal} is supplied as {reference.picture_tag}; define reusable content as "
                f"{reference.subject_tag}. Requested role={reference.role}; retention={reference.retention}; "
                f"existing note={description}"
            )
        detail = DETAIL_GUIDANCE.get("detailed", DETAIL_GUIDANCE["detailed"])
        refs = "\n".join(reference_lines) if reference_lines else "- No reference images are supplied."
        return (
            f"Rewrite the following request for a single still image. {detail}\n\n"
            f"Ordered references:\n{refs}\n\n"
            f"User request:\n{request.prompt}\n\n"
            "Output the four required sections only."
        )

    @classmethod
    def generate(cls, request: VLMRequest) -> VLMResult:
        if len(request.images) != len(request.references):
            raise PromptFormatError(
                f"VLM received {len(request.images)} images for {len(request.references)} reference records."
            )
        torch, _, _ = cls.dependencies()
        handle = cls._load(request)
        pil_images = tuple(cls._to_pil(image) for image in request.images)
        content = []
        for image in pil_images:
            content.append({"type": "image", "image": image})
        content.append({"type": "text", "text": cls._user_instruction(request)})
        messages = [
            {"role": "system", "content": request.system_instruction or IMAGE_REWRITE_SYSTEM_INSTRUCTION},
            {"role": "user", "content": content},
        ]
        processor = handle.processor
        model = handle.model
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=list(pil_images) or None, return_tensors="pt", padding=True)
        if hasattr(inputs, "to"):
            inputs = inputs.to(handle.device)
        generator = None
        try:
            generator = torch.Generator(device=handle.device if handle.device.startswith("cuda") else "cpu")
            generator.manual_seed(int(request.seed))
        except Exception:
            torch.manual_seed(int(request.seed))
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": max(128, min(8192, int(request.max_tokens))),
            "do_sample": request.temperature > 0,
            "temperature": max(0.01, float(request.temperature)),
            "top_p": max(0.05, min(1.0, float(request.top_p))),
            "use_cache": True,
        }
        if generator is not None:
            generation_kwargs["generator"] = generator
        with torch.inference_mode():
            generated = model.generate(**inputs, **generation_kwargs)
        input_length = inputs["input_ids"].shape[1]
        trimmed = generated[:, input_length:]
        output = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[
            0
        ].strip()
        if not request.keep_loaded:
            cls.unload()
        public_kwargs = {key: value for key, value in generation_kwargs.items() if key != "generator"}
        return VLMResult(
            output, request.model_path, handle.device, request.quantization, len(pil_images), public_kwargs
        )


def enhance_state(
    state: StudioState,
    images: Sequence[Any],
    *,
    compiler: PromptCompiler | None = None,
) -> tuple[CompileResult, VLMResult]:
    compiler = compiler or PromptCompiler()
    base = compiler.compile(state)
    request = VLMRequest(
        model_path=state.prompt_options.analyzer_model,
        prompt=state.prompt,
        references=base.references,
        images=tuple(images),
        system_instruction=state.prompt_options.system_instruction or IMAGE_REWRITE_SYSTEM_INSTRUCTION,
        device=state.prompt_options.analyzer_device,
        quantization=state.prompt_options.analyzer_quantization,
        max_tokens=state.prompt_options.analyzer_max_tokens,
        seed=state.generation.seed,
        keep_loaded=state.prompt_options.analyzer_keep_loaded,
    )
    vlm_result = QwenVLAdapter.generate(request)
    enhanced = compiler.accept_enhanced(vlm_result.text, base)
    return enhanced, vlm_result


def compile_with_optional_vlm(
    state: StudioState,
    images: Sequence[Any],
    *,
    compiler: PromptCompiler | None = None,
) -> tuple[CompileResult, str]:
    """Compile safely when the optional standalone analyzer is unconfigured."""

    compiler = compiler or PromptCompiler()
    if state.prompt_options.enhance_mode == "vlm" and state.prompt_options.analyzer_model:
        compile_result, vlm_result = enhance_state(state, images, compiler=compiler)
        return compile_result, f"\n{vlm_result.summary()}"
    compile_result = compiler.compile(state)
    if state.prompt_options.enhance_mode == "vlm":
        return (
            compile_result,
            "\nPrompt enhancement: used the built-in production-brief compiler because no standalone "
            "VLM analyzer model was selected.",
        )
    return compile_result, ""


def adapter_status() -> str:
    handle = QwenVLAdapter._handle
    if not handle:
        return json.dumps({"loaded": False})
    return json.dumps(
        {
            "loaded": True,
            "model_path": handle.signature[0],
            "device": handle.signature[1],
            "quantization": handle.signature[2],
        },
        ensure_ascii=False,
    )
