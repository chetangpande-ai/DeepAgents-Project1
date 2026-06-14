from pathlib import Path
import re
from urllib.parse import urlparse

from test_script_generator.schemas import SourceTestCase, TestStep, WebEvidenceInput


def build_test_case_from_recording(
    app_url: str,
    recording_script_path: str,
    source_id: str | None = None,
    title: str | None = None,
) -> SourceTestCase:
    recording_path = Path(recording_script_path)
    recording_content = recording_path.read_text(encoding="utf-8", errors="ignore")
    steps = _steps_from_recording(recording_content, app_url)
    generated_source_id = source_id or _source_id_from_url(app_url)
    generated_title = title or f"Exploratory flow for {_host_label(app_url)}"

    return SourceTestCase(
        source_id=generated_source_id,
        source_system="exploratory-ui",
        title=generated_title,
        description=(
            "Generated from a tester-led Playwright exploratory recording. "
            "Review assertions before merging."
        ),
        automation_layers=["ui"],
        tags=["exploratory", "playwright-recording"],
        web=WebEvidenceInput(
            app_url=app_url,
            recording_script_path=recording_script_path,
        ),
        steps=steps,
    )


def _steps_from_recording(recording_content: str, app_url: str) -> list[TestStep]:
    steps: list[TestStep] = []
    for line in recording_content.splitlines():
        action = _action_from_line(line.strip(), app_url)
        if action:
            steps.append(
                TestStep(
                    step_number=len(steps) + 1,
                    action=action[0],
                    expected_result=action[1],
                )
            )

    if not steps:
        steps.append(
            TestStep(
                step_number=1,
                action=f"Explore the application at {app_url}.",
                expected_result="The explored application flow is available in the Playwright recording.",
            )
        )
    return steps


def _action_from_line(line: str, app_url: str) -> tuple[str, str] | None:
    if not line or line.startswith("//"):
        return None

    navigate = _first_string_argument(line, "navigate")
    if navigate:
        return (
            f"Open {navigate}.",
            "Page loads successfully.",
        )

    fill_value = _last_string_argument(line, "fill")
    if fill_value is not None:
        field = _target_label(line) or "the field"
        masked_value = "test data" if fill_value else "blank value"
        return (
            f"Enter {masked_value} in {field}.",
            f"{_sentence_case(field)} accepts the entered value.",
        )

    press_value = _last_string_argument(line, "press")
    if press_value is not None:
        target = _target_label(line) or "the focused control"
        return (
            f"Press {press_value} on {target}.",
            "The keyboard action is applied successfully.",
        )

    if ".click(" in line:
        target = _target_label(line) or "the selected control"
        return (
            f"Click {target}.",
            f"{_sentence_case(target)} click completes successfully.",
        )

    if ".check(" in line:
        target = _target_label(line) or "the checkbox"
        return (
            f"Select {target}.",
            f"{_sentence_case(target)} is selected.",
        )

    if ".uncheck(" in line:
        target = _target_label(line) or "the checkbox"
        return (
            f"Clear {target}.",
            f"{_sentence_case(target)} is cleared.",
        )

    selected = _last_string_argument(line, "selectOption")
    if selected is not None:
        target = _target_label(line) or "the dropdown"
        return (
            f"Select {selected} from {target}.",
            f"{_sentence_case(target)} shows the selected value.",
        )

    if "assert" in line.lower() or "expect(" in line:
        target = _target_label(line) or _host_label(app_url)
        return (
            f"Verify {target}.",
            f"{_sentence_case(target)} is displayed as expected.",
        )

    return None


def _target_label(line: str) -> str | None:
    patterns = [
        r"setName\(\"([^\"]+)\"\)",
        r"getByText\(\"([^\"]+)\"",
        r"getByLabel\(\"([^\"]+)\"",
        r"getByPlaceholder\(\"([^\"]+)\"",
        r"getByRole\([^)]*\"([^\"]+)\"",
        r"locator\(\"([^\"]+)\"",
    ]
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return _humanize(match.group(1))
    return None


def _first_string_argument(line: str, method_name: str) -> str | None:
    match = re.search(rf"\.{method_name}\(\"([^\"]*)\"", line)
    return match.group(1) if match else None


def _last_string_argument(line: str, method_name: str) -> str | None:
    match = re.search(rf"\.{method_name}\((.*)\)", line)
    if not match:
        return None
    quoted = re.findall(r"\"([^\"]*)\"", match.group(1))
    return quoted[-1] if quoted else None


def _source_id_from_url(app_url: str) -> str:
    host = _host_label(app_url).upper()
    safe = "".join(char if char.isalnum() else "_" for char in host)
    return f"TC_EXPLORE_{safe or 'APP'}_001"


def _host_label(app_url: str) -> str:
    parsed = urlparse(app_url)
    host = parsed.netloc or parsed.path or "application"
    return host.removeprefix("www.")


def _humanize(value: str) -> str:
    if value.startswith(("#", ".", "[", "//")):
        return f"element {value}"
    return value.strip()


def _sentence_case(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]
