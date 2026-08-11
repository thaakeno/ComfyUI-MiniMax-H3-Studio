from __future__ import annotations

from h3studio.prompting import comfy_analyzer
from h3studio.runtime_guards import _lean_analyze_references, install_runtime_guards


def test_zero_image_t2i_never_loads_optional_prompt_writer() -> None:
    def fail_loader():
        raise AssertionError("zero-image T2I must not stage the helper Qwen model")

    references, prompt, note = _lean_analyze_references(
        None,
        "a quiet cinematic frame",
        (),
        (),
        deep_enhancement=True,
        writer_loader=fail_loader,
        writer_name="qwen3vl_4b_fp8_scaled.safetensors",
    )

    assert references == ()
    assert prompt == "a quiet cinematic frame"
    assert "Prompt writer skipped for zero-image T2I" in note


def test_runtime_guard_installation_is_idempotent() -> None:
    install_runtime_guards()
    first = comfy_analyzer.analyze_references
    install_runtime_guards()
    assert comfy_analyzer.analyze_references is first
    assert getattr(first, "__h3studio_zero_image_guard__", False) is True
