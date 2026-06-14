from pathlib import Path

from test_script_generator.adapters.manual_input import load_test_cases


def test_load_sample_test_cases() -> None:
    cases = load_test_cases(Path("input/test-cases.json"))

    assert len(cases) == 4
    assert cases[0].source_id == "TC_WEB_001"
    assert cases[0].automation_layers == ["ui"]
