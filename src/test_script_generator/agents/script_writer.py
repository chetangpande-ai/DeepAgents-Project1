from pathlib import Path

from test_script_generator.schemas import FrameworkProfile, GeneratedArtifact, SourceTestCase


def generate_artifacts(
    test_cases: list[SourceTestCase],
    planned_ids: list[str],
    framework: FrameworkProfile,
) -> list[GeneratedArtifact]:
    planned = [case for case in test_cases if case.source_id in set(planned_ids)]
    artifacts: list[GeneratedArtifact] = []
    for test_case in planned:
        if framework == "java-bdd-maven":
            artifacts.extend(_bdd_artifacts(test_case))
        else:
            artifacts.append(_testng_artifact(test_case))
    return artifacts


def _bdd_artifacts(test_case: SourceTestCase) -> list[GeneratedArtifact]:
    recording = _read_recording(test_case)
    recording_path = recording[0] if recording else None
    recording_content = recording[1] if recording else None
    return [
        _feature_artifact(test_case),
        _step_definition_artifact(test_case, recording_path, recording_content),
        _runner_artifact(test_case),
    ]


def _feature_artifact(test_case: SourceTestCase) -> GeneratedArtifact:
    trace_tag = _trace_tag(test_case.source_id)
    lines = [f"@{trace_tag}", f"Feature: {test_case.title}", "", f"  Scenario: {test_case.title}"]
    for step in test_case.steps:
        keyword = "Given" if step.step_number == 1 else "When"
        lines.append(f"    {keyword} {step.action}")
        if step.expected_result:
            lines.append(f"    Then {step.expected_result}")
    return GeneratedArtifact(
        path=f"src/test/resources/features/generated/{trace_tag}.feature",
        artifact_type="feature_file",
        content="\n".join(lines) + "\n",
        related_test_case_ids=[test_case.source_id],
    )


def _testng_artifact(test_case: SourceTestCase) -> GeneratedArtifact:
    trace_tag = _trace_tag(test_case.source_id)
    class_name = f"{_safe_class_part(trace_tag)}GeneratedTest"
    recording = _read_recording(test_case)
    lines = [
        "package generated;",
        "",
        "import org.testng.annotations.Test;",
        "",
        f"public class {class_name} {{",
        f'    @Test(description = "{trace_tag} - {test_case.title}")',
        "    public void generatedScenario() {",
    ]
    for step in test_case.steps:
        lines.append(f"        // Step {step.step_number}: {step.action}")
        if step.expected_result:
            lines.append(f"        // Expected: {step.expected_result}")
    if recording:
        lines.extend(
            [
                "",
                f"        // Recorded Playwright evidence from: {recording[0]}",
                "        // Refactor these actions into page objects or reusable helpers.",
            ]
        )
        lines.extend(_java_comment_block(recording[1], indent="        ", max_lines=80))
    lines.extend(["    }", "}"])
    return GeneratedArtifact(
        path=f"src/test/java/generated/{class_name}.java",
        artifact_type="test_class",
        content="\n".join(lines) + "\n",
        related_test_case_ids=[test_case.source_id],
    )


def _step_definition_artifact(
    test_case: SourceTestCase,
    recording_path: str | None,
    recording_content: str | None,
) -> GeneratedArtifact:
    trace_tag = _trace_tag(test_case.source_id)
    class_name = f"{_safe_class_part(trace_tag)}Steps"
    lines = [
        "package generated.steps;",
        "",
        "import io.cucumber.java.en.Given;",
        "import io.cucumber.java.en.Then;",
        "import io.cucumber.java.en.When;",
        "",
        f"public class {class_name} {{",
        f"    // Traceability: {trace_tag}",
        "    // Replace generated method bodies with calls to page objects, API clients, or DB helpers.",
        "",
    ]
    if recording_path and recording_content:
        lines.extend(
            [
                f"    // Recorded Playwright evidence from: {recording_path}",
                "    // Move stable interactions into page objects before merging.",
                "",
            ]
        )

    for step in test_case.steps:
        action_annotation = "Given" if step.step_number == 1 else "When"
        lines.extend(
            [
                f'    @{action_annotation}("{_cucumber_text(step.action)}")',
                f"    public void step{step.step_number}Action() {{",
                "        // TODO: Implement using page objects and the recorded evidence below.",
                "    }",
                "",
            ]
        )
        if step.expected_result:
            lines.extend(
                [
                    f'    @Then("{_cucumber_text(step.expected_result)}")',
                    f"    public void step{step.step_number}ExpectedResult() {{",
                    "        // TODO: Implement assertion using framework helpers.",
                    "    }",
                    "",
                ]
            )

    if recording_content:
        lines.append("    /*")
        lines.append("     * Recorded Playwright code:")
        lines.extend(_block_comment_lines(recording_content, indent="     * ", max_lines=120))
        lines.append("     */")
    lines.append("}")
    return GeneratedArtifact(
        path=f"src/test/java/generated/steps/{class_name}.java",
        artifact_type="step_definition",
        content="\n".join(lines) + "\n",
        related_test_case_ids=[test_case.source_id],
    )


def _runner_artifact(test_case: SourceTestCase) -> GeneratedArtifact:
    trace_tag = _trace_tag(test_case.source_id)
    class_name = f"{_safe_class_part(trace_tag)}Runner"
    lines = [
        "package generated.runners;",
        "",
        "import io.cucumber.junit.Cucumber;",
        "import io.cucumber.junit.CucumberOptions;",
        "import org.junit.runner.RunWith;",
        "",
        "@RunWith(Cucumber.class)",
        "@CucumberOptions(",
        '    features = "src/test/resources/features/generated",',
        '    glue = {"generated.steps"},',
        f'    tags = "@{trace_tag}",',
        "    plugin = {\"pretty\", \"html:target/cucumber-reports/" + trace_tag + "\"}",
        ")",
        f"public class {class_name} {{",
        "}",
    ]
    return GeneratedArtifact(
        path=f"src/test/java/generated/runners/{class_name}.java",
        artifact_type="runner",
        content="\n".join(lines) + "\n",
        related_test_case_ids=[test_case.source_id],
    )


def _read_recording(test_case: SourceTestCase) -> tuple[str, str] | None:
    if not test_case.web or not test_case.web.recording_script_path:
        return None

    path = Path(test_case.web.recording_script_path)
    if not path.exists() or path.stat().st_size == 0:
        return None

    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        return None
    return str(path), content


def _java_comment_block(content: str, indent: str, max_lines: int) -> list[str]:
    return [f"{indent}// {line}" if line else f"{indent}//" for line in content.splitlines()[:max_lines]]


def _block_comment_lines(content: str, indent: str, max_lines: int) -> list[str]:
    return [
        f"{indent}{line.replace('*/', '* /')}" if line else indent.rstrip()
        for line in content.splitlines()[:max_lines]
    ]


def _cucumber_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _trace_tag(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)
    if safe.upper().startswith("TC_"):
        return safe
    return f"TC_{safe}"


def _safe_class_part(value: str) -> str:
    safe = "".join(char for char in value if char.isalnum())
    return safe or "Manual"
