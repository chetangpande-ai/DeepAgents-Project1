from pathlib import Path

from test_script_generator.config import Settings
from test_script_generator.graph import run_workflow
from test_script_generator.schemas import GeneratorState


def test_workflow_creates_report(tmp_path: Path) -> None:
    settings = Settings(
        input_testcase_file=Path("input/test-cases.json"),
        automation_repo_path=tmp_path / "missing-repo",
        dry_run=True,
    )
    state = GeneratorState(input_file=settings.input_testcase_file, run_dir=tmp_path / "run")

    result = run_workflow(state, settings)

    assert result.final_report_path is not None
    assert result.final_report_path.exists()
    assert "TC_TRADE_001" in result.generation_plan.blocked_test_case_ids
    assert "TC_WEB_001" in result.generation_plan.recording_required_test_case_ids
