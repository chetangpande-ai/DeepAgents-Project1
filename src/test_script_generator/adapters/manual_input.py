import csv
import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from test_script_generator.schemas import SourceTestCase, TestStep


def load_test_cases(path: Path) -> list[SourceTestCase]:
    if not path.exists():
        raise FileNotFoundError(f"Input testcase file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif suffix == ".csv":
        raw = _read_csv(path)
    elif suffix in {".md", ".markdown"}:
        raw = _read_markdown(path)
    else:
        raise ValueError(f"Unsupported input file type: {suffix}")

    items = raw.get("test_cases", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("Input must contain a list or a top-level 'test_cases' list.")

    return [_normalize_test_case(item) for item in items]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    cases: list[dict[str, Any]] = []
    for row in rows:
        source_id = row.get("source_id") or row.get("id") or row.get("test_case_id")
        if not source_id:
            raise ValueError("CSV rows must include source_id, id, or test_case_id.")
        cases.append(
            {
                "source_id": source_id,
                "title": row.get("title") or row.get("name") or f"Test case {source_id}",
                "description": row.get("description"),
                "automation_layers": _split_csv_cell(row.get("automation_layers")),
                "tags": _split_csv_cell(row.get("tags")),
                "steps": [
                    {
                        "step_number": 1,
                        "action": row.get("action") or row.get("steps") or "",
                        "expected_result": row.get("expected_result"),
                    }
                ],
            }
        )
    return cases


def _read_markdown(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    title = _first_markdown_heading(text) or path.stem
    return [
        {
            "source_id": path.stem,
            "title": title,
            "description": text,
            "steps": _steps_from_text(text),
        }
    ]


def _normalize_test_case(item: dict[str, Any]) -> SourceTestCase:
    normalized = dict(item)
    normalized["steps"] = _normalize_steps(item.get("steps", []))
    normalized["description"] = _html_to_text(item.get("description"))
    return SourceTestCase.model_validate(normalized)


def _normalize_steps(raw_steps: Any) -> list[TestStep]:
    if isinstance(raw_steps, str):
        return _steps_from_text(raw_steps)

    if not isinstance(raw_steps, list):
        raise ValueError("Test case steps must be a list or string.")

    steps: list[TestStep] = []
    for index, step in enumerate(raw_steps, start=1):
        if isinstance(step, str):
            steps.append(
                TestStep(
                    step_number=index,
                    action=_html_to_text(step) or "",
                    expected_result=None,
                )
            )
            continue

        if not isinstance(step, dict):
            raise ValueError("Each step must be a string or object.")

        steps.append(
            TestStep(
                step_number=int(step.get("step_number") or index),
                action=_html_to_text(step.get("action")) or "",
                expected_result=_html_to_text(step.get("expected_result")),
                test_data=step.get("test_data") or {},
            )
        )
    return steps


def _steps_from_text(text: str) -> list[TestStep]:
    clean = _html_to_text(text) or ""
    lines = [line.strip("-* 1234567890.\t") for line in clean.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return []
    return [
        TestStep(step_number=index, action=line, expected_result=None)
        for index, line in enumerate(lines, start=1)
    ]


def _html_to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "lxml")
        return soup.get_text(separator="\n", strip=True)
    return text.strip()


def _first_markdown_heading(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def _split_csv_cell(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
