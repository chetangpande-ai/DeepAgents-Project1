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
            artifacts.append(_feature_artifact(test_case))
        else:
            artifacts.append(_testng_artifact(test_case))
    return artifacts


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
    lines.extend(["    }", "}"])
    return GeneratedArtifact(
        path=f"src/test/java/generated/{class_name}.java",
        artifact_type="test_class",
        content="\n".join(lines) + "\n",
        related_test_case_ids=[test_case.source_id],
    )


def _trace_tag(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)
    if safe.upper().startswith("TC_"):
        return safe
    return f"TC_{safe}"


def _safe_class_part(value: str) -> str:
    safe = "".join(char for char in value if char.isalnum())
    return safe or "Manual"
