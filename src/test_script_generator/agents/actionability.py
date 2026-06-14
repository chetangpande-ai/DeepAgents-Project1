from pathlib import Path

from test_script_generator.adapters.api_evidence import validate_api_evidence
from test_script_generator.adapters.db_evidence import validate_db_evidence
from test_script_generator.schemas import ActionabilityAssessment, SourceTestCase


VAGUE_ACTIONS = {
    "place trade",
    "submit request",
    "process transaction",
    "validate record",
    "perform trade",
    "create order",
}


def assess_test_case(test_case: SourceTestCase, base_dir: Path) -> ActionabilityAssessment:
    ambiguity_types: list[str] = []
    missing_details: list[str] = []
    questions: list[str] = []
    requires_web_recording = False
    recording_reason: str | None = None
    vague_business_flow = _is_vague_business_flow(test_case)

    if vague_business_flow:
        ambiguity_types.extend(
            [
                "functional ambiguity",
                "validation ambiguity",
                "test data ambiguity",
                "locator ambiguity",
            ]
        )
        missing_details.extend(
            [
                "business workflow steps",
                "input data",
                "actor or user role",
                "navigation path",
                "success assertion",
            ]
        )
        questions.extend(_trade_questions() if "trade" in _combined_text(test_case) else _generic_questions())

        return ActionabilityAssessment(
            test_case_id=test_case.source_id,
            status="blocked",
            ambiguity_types=_dedupe(ambiguity_types),
            missing_details=_dedupe(missing_details),
            blocking_questions=_dedupe(questions),
            generation_allowed=False,
            skeleton_allowed=False,
            requires_web_recording=False,
        )

    layers = set(test_case.automation_layers)
    if "ui" in layers:
        web = test_case.web
        if web and web.recording_script_path:
            recording_path = _resolve_path(web.recording_script_path, base_dir)
            if not recording_path.exists():
                requires_web_recording = True
                recording_reason = (
                    "Recorded Playwright script was provided, but the file does not exist yet."
                )
                missing_details.append(f"recorded Playwright script not found: {recording_path}")
                questions.append("Run Playwright codegen, close the recorder, then retry generation.")
            elif recording_path.stat().st_size == 0:
                requires_web_recording = True
                recording_reason = "Recorded Playwright script exists, but it is empty."
                missing_details.append(f"recorded Playwright script is empty: {recording_path}")
                questions.append("Finish the Playwright recording, close the recorder, then retry generation.")
        elif web and web.record_missing_steps and web.app_url:
            requires_web_recording = True
            recording_reason = "Clear web scenario needs Playwright codegen evidence before Java script generation."
        elif _looks_like_clear_ui_flow(test_case):
            missing_details.append("stable web locators or Playwright recording")
            questions.append("Provide Playwright recording or stable locators for the web flow.")
        else:
            missing_details.append("web app URL, navigation path, or recorded UI steps")
            questions.append("Provide app URL and record the missing UI steps with Playwright codegen.")

    api_missing = validate_api_evidence(test_case, base_dir)
    if api_missing:
        ambiguity_types.append("api evidence ambiguity")
        missing_details.extend(api_missing)

    db_missing = validate_db_evidence(test_case)
    if db_missing:
        ambiguity_types.append("db validation ambiguity")
        missing_details.extend(db_missing)

    missing_details = _dedupe(missing_details)
    questions = _dedupe(questions)
    ambiguity_types = _dedupe(ambiguity_types)

    if any(
        detail.startswith(("API", "DB")) or "missing" in detail.lower()
        for detail in missing_details
        if not requires_web_recording
    ):
        return ActionabilityAssessment(
            test_case_id=test_case.source_id,
            status="blocked",
            ambiguity_types=ambiguity_types,
            missing_details=missing_details,
            blocking_questions=questions,
            generation_allowed=False,
            skeleton_allowed=False,
            requires_web_recording=False,
        )

    if requires_web_recording:
        return ActionabilityAssessment(
            test_case_id=test_case.source_id,
            status="partial",
            ambiguity_types=ambiguity_types or ["locator ambiguity"],
            missing_details=missing_details,
            blocking_questions=questions,
            generation_allowed=False,
            skeleton_allowed=False,
            requires_web_recording=True,
            recording_reason=recording_reason,
        )

    return ActionabilityAssessment(
        test_case_id=test_case.source_id,
        status="ready",
        ambiguity_types=ambiguity_types,
        missing_details=missing_details,
        blocking_questions=questions,
        generation_allowed=True,
        skeleton_allowed=False,
    )


def _is_vague_business_flow(test_case: SourceTestCase) -> bool:
    layers = set(test_case.automation_layers)
    if layers and layers.issubset({"api", "db"}):
        return False

    text = _combined_text(test_case)
    if any(action in text for action in VAGUE_ACTIONS):
        return True
    if len(test_case.steps) < 2 and any(word in text for word in {"trade", "submit", "process"}):
        return True
    return False


def _looks_like_clear_ui_flow(test_case: SourceTestCase) -> bool:
    return len(test_case.steps) >= 3


def _combined_text(test_case: SourceTestCase) -> str:
    parts = [test_case.title, test_case.description or ""]
    for step in test_case.steps:
        parts.append(step.action)
        parts.append(step.expected_result or "")
    return " ".join(parts).lower()


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def _trade_questions() -> list[str]:
    return [
        "Which trade type should be placed: equity, option, future, forex, or another instrument type?",
        "What instrument or symbol should be used?",
        "What account and user role should place the trade?",
        "Is the order buy, sell, short sell, or cover?",
        "What order type, quantity, price, and time-in-force should be entered?",
        "Which screens are involved in the trading workflow?",
        "What exact signal proves success: order ID, confirmation message, order status, API response, or DB record?",
    ]


def _generic_questions() -> list[str]:
    return [
        "What exact user or system actions are required?",
        "What input data should be used?",
        "Which screen, endpoint, or database object is involved?",
        "What exact validation proves success?",
    ]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
