from fastapi.testclient import TestClient

from test_script_generator.web_api import app


def test_generate_endpoint_returns_logs_and_approvals() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/generate",
        json={
            "framework_profile": "java-bdd-maven",
            "dry_run": True,
            "test_case": {
                "source_id": "TC_UI_100",
                "title": "Checkout invalid coupon",
                "automation_layers": ["ui"],
                "web": {
                    "record_missing_steps": True,
                    "app_url": "https://test.example.com",
                },
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Login as valid customer.",
                        "expected_result": "Customer lands on home page.",
                    },
                    {
                        "step_number": 2,
                        "action": "Apply invalid coupon.",
                        "expected_result": "Invalid coupon error is displayed.",
                    },
                    {
                        "step_number": 3,
                        "action": "Submit checkout.",
                        "expected_result": "Order is not submitted.",
                    },
                ],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["logs"]
    assert body["approvals"][0]["kind"] == "playwright_recording"
    assert body["web_recordings"][0]["test_case_id"] == "TC_UI_100"
    assert "npx playwright codegen" in " ".join(body["web_recordings"][0]["command"])
    assert body["generated_artifacts"] == []


def test_recording_launcher_rejects_non_playwright_command() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/recordings/start",
        json={"command": ["powershell", "-Command", "Get-ChildItem"]},
    )

    assert response.status_code == 400


def test_recording_launcher_surfaces_immediate_playwright_failure(monkeypatch) -> None:
    client = TestClient(app)

    class FailedProcess:
        pid = 12345

        def poll(self) -> int:
            return 1

    def fake_popen(command, stdout, stderr, **kwargs):
        stdout.write("Executable doesn't exist. Please run: npx playwright install\n")
        stdout.flush()
        return FailedProcess()

    monkeypatch.setattr("test_script_generator.web_api.subprocess.Popen", fake_popen)
    monkeypatch.setattr("test_script_generator.web_api.time.sleep", lambda _: None)

    response = client.post(
        "/api/recordings/start",
        json={
            "command": [
                "npx",
                "playwright",
                "codegen",
                "--target",
                "java",
                "--output",
                ".tsg-runs/test-recorder-failure/playwright-codegen.java",
                "https://example.com",
            ]
        },
    )

    assert response.status_code == 400
    assert "npx playwright install chromium" in response.json()["detail"]


def test_exploratory_prepare_returns_recording_task() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/exploratory/prepare",
        json={
            "framework_profile": "java-bdd-maven",
            "app_url": "https://example.com/login",
            "source_id": "TC_EXPLORE_PREP_001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recording"]["test_case_id"] == "TC_EXPLORE_PREP_001"
    assert "npx playwright codegen" in " ".join(body["recording"]["command"])


def test_exploratory_generate_converts_recording_to_scripts(tmp_path) -> None:
    client = TestClient(app)
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

    response = client.post(
        "/api/exploratory/generate",
        json={
            "framework_profile": "java-bdd-maven",
            "dry_run": True,
            "app_url": "https://example.com/login",
            "recording_script_path": str(recording),
            "source_id": "TC_EXPLORE_LOGIN_001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generated_test_case"]["source_id"] == "TC_EXPLORE_LOGIN_001"
    assert body["generated_test_case"]["steps"][1]["action"] == "Enter test data in Mobile Number."
    assert {artifact["artifact_type"] for artifact in body["generated_artifacts"]} == {
        "feature_file",
        "step_definition",
        "runner",
    }
