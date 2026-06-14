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
    assert body["generated_artifacts"] == []
