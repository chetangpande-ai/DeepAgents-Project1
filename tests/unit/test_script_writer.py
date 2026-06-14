from pathlib import Path

from test_script_generator.adapters.manual_input import load_test_cases
from test_script_generator.agents.script_writer import generate_artifacts
from test_script_generator.schemas import WebEvidenceInput


def test_bdd_writer_generates_feature_steps_and_runner_without_recording() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    api_case = next(case for case in cases if case.source_id == "TC_API_001")

    artifacts = generate_artifacts([api_case], [api_case.source_id], "java-bdd-maven")
    artifact_types = {artifact.artifact_type for artifact in artifacts}

    assert artifact_types == {"feature_file", "step_definition", "runner"}
    step_definition = next(
        artifact for artifact in artifacts if artifact.artifact_type == "step_definition"
    )
    runner = next(artifact for artifact in artifacts if artifact.artifact_type == "runner")
    assert "@When" in step_definition.content or "@Given" in step_definition.content
    assert "TODO: Implement" in step_definition.content
    assert "@RunWith(Cucumber.class)" in runner.content
    assert 'glue = {"generated.steps"}' in runner.content


def test_bdd_writer_includes_recorded_playwright_evidence(tmp_path: Path) -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    web_case = next(case for case in cases if case.source_id == "TC_WEB_001")
    recording_script = tmp_path / "playwright-codegen.java"
    recording_script.write_text("page.click(\"text=Checkout\");\n", encoding="utf-8")
    web_case = web_case.model_copy(
        update={
            "web": WebEvidenceInput(
                app_url="https://test.example.com",
                recording_script_path=str(recording_script),
            )
        }
    )

    artifacts = generate_artifacts([web_case], [web_case.source_id], "java-bdd-maven")

    step_definition = next(
        artifact for artifact in artifacts if artifact.artifact_type == "step_definition"
    )
    assert "Recorded Playwright evidence" in step_definition.content
    assert "page.click" in step_definition.content
