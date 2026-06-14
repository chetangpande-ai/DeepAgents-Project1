from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from test_script_generator.adapters.filesystem import create_run_dir
from test_script_generator.config import Settings
from test_script_generator.graph import run_workflow
from test_script_generator.reports.markdown import render_markdown_report
from test_script_generator.schemas import (
    FrameworkProfile,
    GeneratedArtifact,
    GeneratorState,
    SourceTestCase,
    ValidationResult,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StageLog(BaseModel):
    stage: str
    status: Literal["complete", "warning", "blocked", "skipped"]
    message: str
    timestamp: str = Field(default_factory=_utc_now)


class ApprovalNotice(BaseModel):
    kind: Literal["clarification", "playwright_recording", "review", "pr"]
    severity: Literal["info", "warning", "blocked"]
    title: str
    message: str
    test_case_id: str | None = None


class GenerateRequest(BaseModel):
    test_case: SourceTestCase
    framework_profile: FrameworkProfile = "java-bdd-maven"
    automation_repo_path: str | None = None
    dry_run: bool = True


class GenerateResponse(BaseModel):
    run_dir: str
    report_path: str | None
    report_markdown: str
    framework_profile: FrameworkProfile | None
    logs: list[StageLog]
    approvals: list[ApprovalNotice]
    generated_artifacts: list[GeneratedArtifact]
    validation_result: ValidationResult | None


app = FastAPI(title="Test Script Generator API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    settings = Settings()
    settings.default_framework_profile = request.framework_profile
    settings.dry_run = request.dry_run
    if request.automation_repo_path:
        settings.automation_repo_path = Path(request.automation_repo_path)

    run_dir = create_run_dir()
    state = GeneratorState(
        run_dir=run_dir,
        test_cases=[request.test_case],
        framework_profile=request.framework_profile,
    )
    result = run_workflow(state, settings)
    report = render_markdown_report(result)

    return GenerateResponse(
        run_dir=str(run_dir),
        report_path=str(result.final_report_path) if result.final_report_path else None,
        report_markdown=report,
        framework_profile=result.framework_profile,
        logs=_build_stage_logs(result),
        approvals=_build_approval_notices(result),
        generated_artifacts=result.artifacts,
        validation_result=result.validation_result,
    )


def _build_stage_logs(state: GeneratorState) -> list[StageLog]:
    logs = [
        StageLog(
            stage="Input",
            status="complete",
            message=f"Received {len(state.test_cases)} testcase(s).",
        ),
        StageLog(
            stage="Framework",
            status="complete",
            message=f"Selected {state.framework_profile}.",
        ),
    ]

    if state.repo_profile and state.repo_profile.warnings:
        logs.append(
            StageLog(
                stage="Repository scan",
                status="warning",
                message="; ".join(state.repo_profile.warnings),
            )
        )
    else:
        logs.append(
            StageLog(
                stage="Repository scan",
                status="complete",
                message="Automation repository profile created.",
            )
        )

    for assessment in state.actionability_assessments:
        status: Literal["complete", "warning", "blocked", "skipped"]
        if assessment.status == "blocked":
            status = "blocked"
        elif assessment.requires_web_recording:
            status = "warning"
        else:
            status = "complete"
        logs.append(
            StageLog(
                stage=f"Actionability: {assessment.test_case_id}",
                status=status,
                message=_assessment_message(assessment),
            )
        )

    logs.append(
        StageLog(
            stage="Generation plan",
            status="complete",
            message=(
                f"{len(state.generation_plan.planned_test_case_ids)} planned, "
                f"{len(state.generation_plan.blocked_test_case_ids)} blocked, "
                f"{len(state.generation_plan.recording_required_test_case_ids)} need recording."
            ),
        )
    )

    logs.append(
        StageLog(
            stage="Generated output",
            status="complete" if state.artifacts else "skipped",
            message=f"{len(state.artifacts)} artifact(s) generated.",
        )
    )

    if state.validation_result:
        validation_status: Literal["complete", "warning", "blocked", "skipped"]
        if state.validation_result.skipped:
            validation_status = "skipped"
        elif state.validation_result.passed:
            validation_status = "complete"
        else:
            validation_status = "blocked"
        validation_message = (
            "; ".join(state.validation_result.errors)
            if state.validation_result.errors
            else "Validation completed."
        )
        logs.append(
            StageLog(
                stage="Validation",
                status=validation_status,
                message=validation_message,
            )
        )

    logs.append(
        StageLog(
            stage="Report",
            status="complete",
            message=f"Report written to {state.final_report_path}.",
        )
    )
    return logs


def _build_approval_notices(state: GeneratorState) -> list[ApprovalNotice]:
    notices: list[ApprovalNotice] = []
    for assessment in state.actionability_assessments:
        if assessment.status == "blocked":
            notices.append(
                ApprovalNotice(
                    kind="clarification",
                    severity="blocked",
                    title="Clarification required",
                    message="; ".join(assessment.blocking_questions or assessment.missing_details),
                    test_case_id=assessment.test_case_id,
                )
            )
        if assessment.requires_web_recording:
            notices.append(
                ApprovalNotice(
                    kind="playwright_recording",
                    severity="warning",
                    title="Playwright recording required",
                    message=assessment.recording_reason
                    or "Record missing web steps before script generation.",
                    test_case_id=assessment.test_case_id,
                )
            )

    if state.artifacts:
        notices.append(
            ApprovalNotice(
                kind="review",
                severity="info",
                title="Manual review required",
                message="Review generated artifacts before enabling repo writes or PR creation.",
            )
        )
    return notices


def _assessment_message(assessment) -> str:
    if assessment.status == "blocked":
        return "Blocked: " + ", ".join(assessment.missing_details)
    if assessment.requires_web_recording:
        return assessment.recording_reason or "Playwright recording required."
    return "Ready for generation."

