from h3studio.console_report import format_execution_report
from h3studio.context import H3StudioContext
from h3studio.prompting.compiler import PromptCompiler
from h3studio.references import ReferenceImage
from h3studio.routing import choose_route
from h3studio.state import GenerationOptions, PromptOptions, StudioState


def test_console_report_includes_config_references_and_both_prompts() -> None:
    state = StudioState(
        prompt="Keep @Image 1 as the subject in a cinematic portrait.",
        references=(ReferenceImage("ref-1", "face.png", 1, role="identity", retention="fully_preserved"),),
        prompt_options=PromptOptions(enhance_mode="compile_only", adherence=0.85),
        generation=GenerationOptions(seed=42, aspect_ratio="4:5", megapixels=0.8),
    )
    compiled = PromptCompiler().compile(state)
    context = H3StudioContext.create(
        state,
        compiled,
        state.generation.resolution(),
        choose_route("auto", compiled.resolved_mode, 1),
        (object(),),
        ("face.png",),
    )
    report = format_execution_report(context)
    assert "H3 STUDIO EXECUTION" in report
    assert "Seed          : 42" in report
    assert "@Image 1: face.png | role=identity | retention=fully_preserved" in report
    assert "Original prompt:" in report
    assert "Compiled H3 prompt:" in report
    assert "<Picture 1>" in report
