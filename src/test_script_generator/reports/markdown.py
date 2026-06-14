from test_script_generator.schemas import GeneratorState


def render_markdown_report(state: GeneratorState) -> str:
    lines = [
        "# Test Script Generator Report",
        "",
        f"Input file: `{state.input_file}`",
        f"Framework: `{state.framework_profile}`",
        "",
        "## Actionability",
        "",
    ]
    for assessment in state.actionability_assessments:
        lines.extend(
            [
                f"### {assessment.test_case_id}",
                "",
                f"- Status: `{assessment.status}`",
                f"- Generation allowed: `{assessment.generation_allowed}`",
                f"- Requires Playwright recording: `{assessment.requires_web_recording}`",
            ]
        )
        if assessment.missing_details:
            lines.append(f"- Missing details: {', '.join(assessment.missing_details)}")
        if assessment.blocking_questions:
            lines.append("- Blocking questions:")
            lines.extend(f"  - {question}" for question in assessment.blocking_questions)
        lines.append("")

    lines.extend(["## Generation Plan", ""])
    lines.append(f"- Planned: {', '.join(state.generation_plan.planned_test_case_ids) or 'none'}")
    lines.append(f"- Blocked: {', '.join(state.generation_plan.blocked_test_case_ids) or 'none'}")
    lines.append(
        f"- Needs recording: {', '.join(state.generation_plan.recording_required_test_case_ids) or 'none'}"
    )
    if state.generation_plan.notes:
        lines.append("- Notes:")
        lines.extend(f"  - {note}" for note in state.generation_plan.notes)
    lines.append("")

    if state.web_recordings:
        lines.extend(["## Playwright Recording Requests", ""])
        for recording in state.web_recordings:
            lines.append(f"### {recording.test_case_id}")
            lines.append(f"- App URL: `{recording.app_url}`")
            lines.append(f"- Notes: `{recording.notes_path}`")
            lines.append(f"- Target script: `{recording.recording_script_path}`")
            lines.append(f"- Command: `{' '.join(recording.command)}`")
            lines.append("")

    lines.extend(["## Generated Artifacts", ""])
    if not state.artifacts:
        lines.append("No script artifacts generated in this run.")
    for artifact in state.artifacts:
        lines.append(f"- `{artifact.path}` ({artifact.artifact_type})")
    lines.append("")

    if state.publish_result:
        lines.extend(
            [
                "## Repository Publish",
                "",
                f"- Status: `{state.publish_result.status}`",
                f"- Repository: `{state.publish_result.repository}`",
                f"- Branch: `{state.publish_result.branch_name}`",
                f"- Commit: `{state.publish_result.commit_sha}`",
                f"- Pull request: `{state.publish_result.pull_request_url}`",
                f"- Message: {state.publish_result.message}",
            ]
        )
        if state.publish_result.written_paths:
            lines.append("- Written paths:")
            lines.extend(f"  - `{path}`" for path in state.publish_result.written_paths)
        if state.publish_result.errors:
            lines.append(f"- Errors: {', '.join(state.publish_result.errors)}")
        lines.append("")

    if state.validation_result:
        lines.extend(
            [
                "## Validation",
                "",
                f"- Passed: `{state.validation_result.passed}`",
                f"- Skipped: `{state.validation_result.skipped}`",
            ]
        )
        if state.validation_result.errors:
            lines.append(f"- Errors: {', '.join(state.validation_result.errors)}")

    return "\n".join(lines) + "\n"
