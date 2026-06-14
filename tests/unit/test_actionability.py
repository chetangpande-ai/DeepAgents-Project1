from pathlib import Path

from test_script_generator.adapters.manual_input import load_test_cases
from test_script_generator.agents.actionability import assess_test_case
from test_script_generator.schemas import WebEvidenceInput


def test_vague_place_trade_is_blocked() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    trade_case = next(case for case in cases if case.source_id == "TC_TRADE_001")

    assessment = assess_test_case(trade_case, Path("."))

    assert assessment.status == "blocked"
    assert assessment.generation_allowed is False
    assert "business workflow steps" in assessment.missing_details


def test_clear_web_case_routes_to_playwright_recording() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    web_case = next(case for case in cases if case.source_id == "TC_WEB_001")

    assessment = assess_test_case(web_case, Path("."))

    assert assessment.status == "partial"
    assert assessment.requires_web_recording is True
    assert assessment.generation_allowed is False


def test_missing_recording_script_path_does_not_allow_generation(tmp_path: Path) -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    web_case = next(case for case in cases if case.source_id == "TC_WEB_001")
    missing_script = tmp_path / "playwright-codegen.java"
    web_case = web_case.model_copy(
        update={
            "web": WebEvidenceInput(
                app_url="https://test.example.com",
                recording_script_path=str(missing_script),
            )
        }
    )

    assessment = assess_test_case(web_case, Path("."))

    assert assessment.status == "partial"
    assert assessment.requires_web_recording is True
    assert assessment.generation_allowed is False
    assert "recorded Playwright script not found" in assessment.missing_details[0]


def test_existing_recording_script_allows_generation(tmp_path: Path) -> None:
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

    assessment = assess_test_case(web_case, Path("."))

    assert assessment.status == "ready"
    assert assessment.requires_web_recording is False
    assert assessment.generation_allowed is True


def test_api_case_with_payload_is_ready() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    api_case = next(case for case in cases if case.source_id == "TC_API_001")

    assessment = assess_test_case(api_case, Path("."))

    assert assessment.status == "ready"
    assert assessment.generation_allowed is True


def test_db_case_with_query_and_validation_points_is_ready() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))
    db_case = next(case for case in cases if case.source_id == "TC_DB_001")

    assessment = assess_test_case(db_case, Path("."))

    assert assessment.status == "ready"
    assert assessment.generation_allowed is True
