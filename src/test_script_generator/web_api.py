from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from test_script_generator.adapters.filesystem import create_run_dir
from test_script_generator.adapters.playwright_codegen import prepare_recording
from test_script_generator.agents.exploratory import build_test_case_from_recording
from test_script_generator.config import Settings
from test_script_generator.graph import run_workflow
from test_script_generator.reports.markdown import render_markdown_report
from test_script_generator.schemas import (
    FrameworkProfile,
    GeneratedArtifact,
    GeneratorState,
    RepositoryPublishResult,
    SourceTestCase,
    TestStep,
    ValidationResult,
    WebEvidenceInput,
    WebRecordingEvidence,
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
    dry_run: bool | None = None


class GenerateResponse(BaseModel):
    run_dir: str
    report_path: str | None
    report_markdown: str
    framework_profile: FrameworkProfile | None
    logs: list[StageLog]
    approvals: list[ApprovalNotice]
    web_recordings: list[WebRecordingEvidence]
    generated_artifacts: list[GeneratedArtifact]
    validation_result: ValidationResult | None
    publish_result: RepositoryPublishResult | None
    generated_test_case: SourceTestCase | None = None


class ExploratoryPrepareRequest(BaseModel):
    app_url: str
    framework_profile: FrameworkProfile = "java-bdd-maven"
    source_id: str | None = None
    title: str | None = None


class ExploratoryPrepareResponse(BaseModel):
    run_dir: str
    framework_profile: FrameworkProfile
    recording: WebRecordingEvidence


class ExploratoryGenerateRequest(BaseModel):
    app_url: str
    recording_script_path: str
    framework_profile: FrameworkProfile = "java-bdd-maven"
    source_id: str | None = None
    title: str | None = None
    dry_run: bool | None = None


class StartRecordingRequest(BaseModel):
    command: list[str]


class StartRecordingResponse(BaseModel):
    status: Literal["started"]
    pid: int
    message: str


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
    if request.dry_run is not None:
        settings.dry_run = request.dry_run
    if request.automation_repo_path:
        settings.automation_repo_path = Path(request.automation_repo_path)

    run_dir = create_run_dir()
    return _run_generation(
        request.test_case,
        request.framework_profile,
        settings,
        run_dir,
        generated_test_case=None,
    )


@app.post("/api/exploratory/prepare", response_model=ExploratoryPrepareResponse)
def prepare_exploratory_recording(
    request: ExploratoryPrepareRequest,
) -> ExploratoryPrepareResponse:
    settings = Settings()
    settings.default_framework_profile = request.framework_profile
    run_dir = create_run_dir()
    source_id = request.source_id or _exploratory_source_id()
    test_case = SourceTestCase(
        source_id=source_id,
        source_system="exploratory-ui",
        title=request.title or "Exploratory application flow",
        automation_layers=["ui"],
        web=WebEvidenceInput(
            record_missing_steps=True,
            app_url=request.app_url,
        ),
        steps=[
            TestStep(
                step_number=1,
                action=f"Explore the application at {request.app_url}.",
                expected_result="Tester completes an exploratory user journey.",
            )
        ],
    )
    recording = prepare_recording(test_case, settings, run_dir)
    return ExploratoryPrepareResponse(
        run_dir=str(run_dir),
        framework_profile=request.framework_profile,
        recording=recording,
    )


@app.post("/api/exploratory/generate", response_model=GenerateResponse)
def generate_from_exploratory_recording(
    request: ExploratoryGenerateRequest,
) -> GenerateResponse:
    recording_path = Path(request.recording_script_path)
    if not recording_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Recording script does not exist: {recording_path}",
        )
    if recording_path.stat().st_size == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Recording script is empty: {recording_path}",
        )

    settings = Settings()
    settings.default_framework_profile = request.framework_profile
    if request.dry_run is not None:
        settings.dry_run = request.dry_run

    test_case = build_test_case_from_recording(
        app_url=request.app_url,
        recording_script_path=request.recording_script_path,
        source_id=request.source_id,
        title=request.title,
    )
    return _run_generation(
        test_case,
        request.framework_profile,
        settings,
        create_run_dir(),
        generated_test_case=test_case,
    )


def _run_generation(
    test_case: SourceTestCase,
    framework_profile: FrameworkProfile,
    settings: Settings,
    run_dir: Path,
    generated_test_case: SourceTestCase | None,
) -> GenerateResponse:
    state = GeneratorState(
        run_dir=run_dir,
        test_cases=[test_case],
        framework_profile=framework_profile,
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
        web_recordings=result.web_recordings,
        generated_artifacts=result.artifacts,
        validation_result=result.validation_result,
        publish_result=result.publish_result,
        generated_test_case=generated_test_case,
    )


@app.post("/api/recordings/start", response_model=StartRecordingResponse)
def start_recording(request: StartRecordingRequest) -> StartRecordingResponse:
    command = _validated_playwright_command(request.command)
    log_path = _recording_launch_log_path(command)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "cwd": str(Path.cwd()),
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    try:
        with log_path.open("w", encoding="utf-8", errors="ignore") as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                **kwargs,
            )
    except OSError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to start Playwright codegen: {exc}",
        ) from exc

    time.sleep(2)
    return_code = process.poll()
    if return_code is not None:
        launch_output = _read_text_tail(log_path)
        raise HTTPException(
            status_code=400,
            detail=_recording_launch_failure_message(return_code, launch_output, log_path),
        )

    return StartRecordingResponse(
        status="started",
        pid=process.pid,
        message=(
            "Playwright recorder started. Close the recorder window when recording is complete. "
            f"Launch log: {log_path}"
        ),
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

    if state.publish_result:
        publish_status: Literal["complete", "warning", "blocked", "skipped"]
        if state.publish_result.status in {"pushed", "initialized", "pr_created", "prepared"}:
            publish_status = "complete"
        elif state.publish_result.status in {"skipped", "no_changes"}:
            publish_status = "skipped"
        else:
            publish_status = "blocked"
        logs.append(
            StageLog(
                stage="Repository publish",
                status=publish_status,
                message=_publish_message(state.publish_result),
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
                message="Review generated artifacts and repository branch before merging.",
            )
        )
    if state.publish_result and state.publish_result.status == "pr_created":
        notices.append(
            ApprovalNotice(
                kind="pr",
                severity="info",
                title="Pull request created",
                message=state.publish_result.pull_request_url
                or "Generated code pull request was created.",
            )
        )
    elif state.publish_result and state.publish_result.status in {"pushed", "initialized"}:
        notices.append(
            ApprovalNotice(
                kind="pr",
                severity="info",
                title=(
                    "Repository initialized"
                    if state.publish_result.status == "initialized"
                    else "Branch pushed"
                ),
                message=_publish_notice_message(state.publish_result),
            )
        )
    return notices


def _assessment_message(assessment) -> str:
    if assessment.status == "blocked":
        return "Blocked: " + ", ".join(assessment.missing_details)
    if assessment.requires_web_recording:
        return assessment.recording_reason or "Playwright recording required."
    return "Ready for generation."


def _publish_message(publish_result: RepositoryPublishResult) -> str:
    if publish_result.pull_request_url:
        return f"{publish_result.message} {publish_result.pull_request_url}"
    if publish_result.branch_name:
        return f"{publish_result.message} Branch: {publish_result.branch_name}"
    return publish_result.message


def _publish_notice_message(publish_result: RepositoryPublishResult) -> str:
    if publish_result.status == "initialized":
        return (
            f"Generated code initialized {publish_result.repository} "
            f"on branch {publish_result.branch_name}."
        )
    return (
        f"Generated code pushed to {publish_result.repository} "
        f"on branch {publish_result.branch_name}."
    )


def _exploratory_source_id() -> str:
    return datetime.now(timezone.utc).strftime("TC_EXPLORE_%Y%m%d%H%M%S")


def _recording_launch_log_path(command: list[str]) -> Path:
    output_index = command.index("--output")
    output_path = Path(command[output_index + 1])
    return output_path.parent / "playwright-codegen-launch.log"


def _recording_launch_failure_message(
    return_code: int,
    launch_output: str,
    log_path: Path,
) -> str:
    install_hint = ""
    if "playwright install" in launch_output.lower() or "executable doesn't exist" in launch_output.lower():
        install_hint = " Install Playwright browsers with `npx playwright install chromium` and try again."
    details = f" Details: {launch_output}" if launch_output else ""
    return (
        f"Playwright recorder exited immediately with code {return_code}.{install_hint} "
        f"Launch log: {log_path}.{details}"
    )


def _read_text_tail(path: Path, max_chars: int = 2000) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]


def _validated_playwright_command(command: list[str]) -> list[str]:
    if len(command) < 8:
        raise HTTPException(status_code=400, detail="Recording command is incomplete.")

    executable_name = Path(command[0]).name.lower()
    if executable_name not in {"npx", "npx.cmd", "npx.exe"}:
        raise HTTPException(status_code=400, detail="Only npx Playwright codegen commands are allowed.")

    if command[1:5] != ["playwright", "codegen", "--target", "java"]:
        raise HTTPException(status_code=400, detail="Only Java Playwright codegen commands are allowed.")

    if "--output" not in command:
        raise HTTPException(status_code=400, detail="Recording command must include --output.")

    output_index = command.index("--output")
    if output_index + 1 >= len(command):
        raise HTTPException(status_code=400, detail="Recording command is missing the output path.")

    output_path = Path(command[output_index + 1]).resolve()
    runs_root = (Path.cwd() / ".tsg-runs").resolve()
    if runs_root != output_path and runs_root not in output_path.parents:
        raise HTTPException(status_code=400, detail="Recording output must be under .tsg-runs.")

    target_url = command[-1]
    if not target_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Recording target must be an HTTP or HTTPS URL.")

    npx_path = shutil.which("npx.cmd" if os.name == "nt" else "npx") or shutil.which("npx")
    if not npx_path:
        raise HTTPException(status_code=400, detail="npx is not available on this machine.")

    return [npx_path, *command[1:]]
