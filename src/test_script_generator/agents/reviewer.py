from test_script_generator.schemas import GeneratedArtifact


def review_artifacts(artifacts: list[GeneratedArtifact]) -> list[str]:
    warnings: list[str] = []
    for artifact in artifacts:
        if "TODO" in artifact.content:
            warnings.append(f"{artifact.path}: contains TODO text.")
        if not artifact.related_test_case_ids:
            warnings.append(f"{artifact.path}: missing testcase traceability.")
    return warnings
