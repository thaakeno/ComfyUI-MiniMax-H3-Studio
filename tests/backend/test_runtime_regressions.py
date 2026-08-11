from __future__ import annotations

from types import SimpleNamespace

from h3studio.context import H3StudioContext
from h3studio.nodes.preview import _resolve_packed_latent


def test_taeh3_restores_video_latent_from_flattened_video_plus_audio_pack() -> None:
    video_values = 24 * 2 * 66 * 118
    audio_values = 32 * 2 * 8

    class Flat:
        shape = (1, video_values + audio_values)

        def __getitem__(self, key):
            assert key == (slice(None), slice(None, video_values))
            return Sliced()

    class Sliced:
        def reshape(self, shape):
            assert shape == (1, 24, 2, 66, 118)
            return "restored-video"

    class Packed:
        ndim = 3
        shape = (1, 1, video_values + audio_values)

        def reshape(self, shape):
            assert shape == (1, -1)
            return Flat()

    result = _resolve_packed_latent(None, Packed(), [(1, 24, 2, 66, 118), (1, 32, 2, 8)])
    assert result == "restored-video"


def test_compile_only_context_uses_compact_runtime_prompt_not_rendered_report() -> None:
    long_prompt = "cinematic portrait " * 120
    state = SimpleNamespace(
        prompt=long_prompt,
        prompt_options=SimpleNamespace(enhance_mode="compile_only"),
        generation=SimpleNamespace(seed=7, sampling_profile="lightx_er_sde_4"),
    )
    compile_result = SimpleNamespace(
        native_prompt="subject_definitions:\n" + long_prompt + "\n" + long_prompt + "\nproduction discipline boilerplate",
        references=(),
        resolved_mode="text_to_image",
        diagnostics_text=lambda: "",
    )
    context = H3StudioContext(
        schema_version=1,
        state=state,
        compile_result=compile_result,
        resolution=SimpleNamespace(width=1024, height=1024, summary=lambda: "1024x1024"),
        route=SimpleNamespace(summary=lambda: "FL2VA"),
        images=(),
        image_filenames=(),
    )

    assert context.prompt.startswith("Generate one finished still image:")
    assert "subject_definitions:" not in context.prompt
    assert "production discipline boilerplate" not in context.prompt
    assert len(context.prompt) < len(compile_result.native_prompt)
