import json
from pathlib import Path

from test_script_generator.config import Settings
from test_script_generator.schemas import SourceTestCase, WebRecordingEvidence


def prepare_recording(
    test_case: SourceTestCase,
    settings: Settings,
    run_dir: Path,
) -> WebRecordingEvidence:
    if not test_case.web:
        raise ValueError("Web evidence is required before preparing Playwright codegen.")

    app_url = test_case.web.app_url or settings.playwright_app_base_url
    if not app_url:
        raise ValueError("App URL is required before preparing Playwright codegen.")

    recording_dir = run_dir / "recordings" / safe_name(test_case.source_id)
    recording_dir.mkdir(parents=True, exist_ok=True)

    script_path = recording_dir / "playwright-codegen.java"
    notes_path = recording_dir / "recording-notes.md"
    candidates_path = recording_dir / "locator-candidates.json"
    merged_steps_path = recording_dir / "merged-test-steps.json"

    storage_state = test_case.web.storage_state_path or (
        str(settings.playwright_storage_state_path)
        if settings.playwright_storage_state_path
        else None
    )

    command = [
        "npx",
        "playwright",
        "codegen",
        "--target",
        "java",
        "--output",
        str(script_path),
    ]
    if storage_state:
        command.extend(["--load-storage", storage_state])
    command.append(app_url)

    notes_path.write_text(
        "\n".join(
            [
                f"# Playwright Recording Request - {test_case.source_id}",
                "",
                "Run this command and perform the missing web steps:",
                "",
                "```powershell",
                " ".join(command),
                "```",
                "",
                "After recording, rerun the generator with `web.recording_script_path`",
                f"pointing to `{script_path}`.",
            ]
        ),
        encoding="utf-8",
    )
    candidates_path.write_text("[]\n", encoding="utf-8")
    merged_steps_path.write_text(
        json.dumps(
            {
                "source_id": test_case.source_id,
                "steps": [step.model_dump() for step in test_case.steps],
                "recording_script_path": str(script_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return WebRecordingEvidence(
        test_case_id=test_case.source_id,
        app_url=app_url,
        recording_script_path=str(script_path),
        notes_path=str(notes_path),
        storage_state_path=storage_state,
        generated_locator_candidates=[],
        command=command,
    )


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
