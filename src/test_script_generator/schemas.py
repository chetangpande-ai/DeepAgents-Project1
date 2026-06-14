from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FrameworkProfile = Literal["java-testng-maven", "java-bdd-maven"]
AutomationLayer = Literal["ui", "api", "db", "hybrid"]
ActionabilityStatus = Literal["ready", "partial", "blocked"]
PublishStatus = Literal[
    "skipped",
    "prepared",
    "pushed",
    "initialized",
    "pr_created",
    "failed",
    "no_changes",
]


class TestStep(BaseModel):
    step_number: int
    action: str
    expected_result: str | None = None
    test_data: dict[str, str] = Field(default_factory=dict)


class WebEvidenceInput(BaseModel):
    record_missing_steps: bool = False
    app_url: str | None = None
    storage_state_path: str | None = None
    recording_script_path: str | None = None
    notes_path: str | None = None


class ApiEvidenceInput(BaseModel):
    swagger_or_openapi_path: str | None = None
    bruno_collection_path: str | None = None
    endpoint: str | None = None
    method: str | None = None
    request_payload: dict[str, Any] | None = None
    request_payload_path: str | None = None
    expected_status: int | None = None
    expected_response_points: list[str] = Field(default_factory=list)
    auth_profile: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class DbEvidenceInput(BaseModel):
    connection_profile: str | None = None
    query: str | None = None
    named_query: str | None = None
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    validation_points: list[str] = Field(default_factory=list)


class SourceTestCase(BaseModel):
    source_id: str
    source_system: str = "manual"
    title: str
    description: str | None = None
    steps: list[TestStep]
    automation_layers: list[AutomationLayer] = Field(default_factory=list)
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    linked_requirement_ids: list[str] = Field(default_factory=list)
    area_path: str | None = None
    iteration_path: str | None = None
    web: WebEvidenceInput | None = None
    api: ApiEvidenceInput | None = None
    db: DbEvidenceInput | None = None

    @field_validator("source_id", mode="before")
    @classmethod
    def coerce_source_id(cls, value: object) -> str:
        return str(value)

    @field_validator("linked_requirement_ids", mode="before")
    @classmethod
    def coerce_requirement_ids(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]


class RepoProfile(BaseModel):
    root_path: str
    framework_profile: FrameworkProfile
    pom_path: str | None = None
    test_source_roots: list[str] = Field(default_factory=list)
    resource_roots: list[str] = Field(default_factory=list)
    package_conventions: list[str] = Field(default_factory=list)
    existing_helpers: list[str] = Field(default_factory=list)
    existing_page_objects: list[str] = Field(default_factory=list)
    existing_api_clients: list[str] = Field(default_factory=list)
    existing_db_utilities: list[str] = Field(default_factory=list)
    existing_step_definitions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WebRecordingEvidence(BaseModel):
    test_case_id: str
    app_url: str
    recording_script_path: str
    notes_path: str | None = None
    storage_state_path: str | None = None
    generated_locator_candidates: list[str] = Field(default_factory=list)
    command: list[str] = Field(default_factory=list)


class ApiEvidence(BaseModel):
    test_case_id: str
    swagger_or_openapi_path: str | None = None
    bruno_collection_path: str | None = None
    endpoint: str | None = None
    method: str | None = None
    request_payload: dict[str, Any] | None = None
    request_payload_path: str | None = None
    expected_status: int | None = None
    expected_response_points: list[str] = Field(default_factory=list)


class DbValidationEvidence(BaseModel):
    test_case_id: str
    connection_profile: str | None = None
    query: str | None = None
    named_query: str | None = None
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    validation_points: list[str] = Field(default_factory=list)


class GeneratedArtifact(BaseModel):
    path: str
    artifact_type: Literal[
        "test_class",
        "feature_file",
        "step_definition",
        "runner",
        "test_data",
        "report",
    ]
    content: str
    related_test_case_ids: list[str]


class ActionabilityAssessment(BaseModel):
    test_case_id: str
    status: ActionabilityStatus
    ambiguity_types: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    generation_allowed: bool = False
    skeleton_allowed: bool = False
    requires_web_recording: bool = False
    recording_reason: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    skipped: bool = False
    command: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    errors: list[str] = Field(default_factory=list)


class RepositoryPublishResult(BaseModel):
    status: PublishStatus
    provider: str = "github"
    repository: str | None = None
    repo_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    pull_request_url: str | None = None
    written_paths: list[str] = Field(default_factory=list)
    initializes_empty_repository: bool = False
    message: str
    errors: list[str] = Field(default_factory=list)


class GenerationPlan(BaseModel):
    planned_test_case_ids: list[str] = Field(default_factory=list)
    blocked_test_case_ids: list[str] = Field(default_factory=list)
    recording_required_test_case_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GeneratorState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    input_file: Path | None = None
    run_dir: Path | None = None
    requested_test_case_ids: list[str] = Field(default_factory=list)
    test_cases: list[SourceTestCase] = Field(default_factory=list)
    web_recordings: list[WebRecordingEvidence] = Field(default_factory=list)
    api_evidence: list[ApiEvidence] = Field(default_factory=list)
    db_evidence: list[DbValidationEvidence] = Field(default_factory=list)
    actionability_assessments: list[ActionabilityAssessment] = Field(default_factory=list)
    framework_profile: FrameworkProfile | None = None
    repo_profile: RepoProfile | None = None
    generation_plan: GenerationPlan = Field(default_factory=GenerationPlan)
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    validation_result: ValidationResult | None = None
    publish_result: RepositoryPublishResult | None = None
    repair_attempts: int = 0
    blockers: list[str] = Field(default_factory=list)
    final_report_path: Path | None = None
