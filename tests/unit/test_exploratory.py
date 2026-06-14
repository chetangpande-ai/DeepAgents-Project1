from pathlib import Path

from test_script_generator.agents.exploratory import build_test_case_from_recording


def test_build_test_case_from_playwright_recording(tmp_path: Path) -> None:
    recording = tmp_path / "playwright-codegen.java"
    recording.write_text(
        "\n".join(
            [
                'page.navigate("https://example.com/login");',
                'page.getByPlaceholder("Mobile Number").fill("9999999999");',
                'page.getByRole(AriaRole.BUTTON, new Page.GetByRoleOptions().setName("Continue")).click();',
            ]
        ),
        encoding="utf-8",
    )

    test_case = build_test_case_from_recording(
        app_url="https://example.com/login",
        recording_script_path=str(recording),
        source_id="TC_EXPLORE_LOGIN_001",
    )

    assert test_case.source_id == "TC_EXPLORE_LOGIN_001"
    assert test_case.automation_layers == ["ui"]
    assert len(test_case.steps) == 3
    assert test_case.steps[0].action == "Open https://example.com/login."
    assert "Mobile Number" in test_case.steps[1].action
    assert "Continue" in test_case.steps[2].action
