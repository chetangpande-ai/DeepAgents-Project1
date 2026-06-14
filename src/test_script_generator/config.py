from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    mesh_api_key: str | None = Field(default=None, alias="MESH_API_KEY")
    mesh_api_url: str | None = Field(default=None, alias="MESH_API_URL")
    mesh_model: str | None = Field(default=None, alias="MESH_MODEL")
    tsg_temperature: float = Field(default=0.1, alias="TSG_TEMPERATURE")

    input_testcase_file: Path = Field(
        default=Path("./input/test-cases.json"),
        alias="INPUT_TESTCASE_FILE",
    )
    input_evidence_dir: Path = Field(
        default=Path("./input/evidence"),
        alias="INPUT_EVIDENCE_DIR",
    )
    automation_repo_path: Path = Field(
        default=Path("../your-java-automation-repo"),
        alias="AUTOMATION_REPO_PATH",
    )
    default_framework_profile: str = Field(
        default="java-testng-maven",
        alias="DEFAULT_FRAMEWORK_PROFILE",
    )

    dry_run: bool = Field(default=True, alias="DRY_RUN")
    max_repair_attempts: int = Field(default=2, alias="MAX_REPAIR_ATTEMPTS")
    allow_repo_writes: bool = Field(default=True, alias="ALLOW_REPO_WRITES")
    allow_pr_creation: bool = Field(default=False, alias="ALLOW_PR_CREATION")

    playwright_codegen_enabled: bool = Field(
        default=True,
        alias="PLAYWRIGHT_CODEGEN_ENABLED",
    )
    playwright_codegen_output_dir: Path = Field(
        default=Path(".tsg-runs/recordings"),
        alias="PLAYWRIGHT_CODEGEN_OUTPUT_DIR",
    )
    playwright_app_base_url: str | None = Field(
        default=None,
        alias="PLAYWRIGHT_APP_BASE_URL",
    )
    playwright_storage_state_path: Path | None = Field(
        default=None,
        alias="PLAYWRIGHT_STORAGE_STATE_PATH",
    )

    api_contracts_dir: Path = Field(
        default=Path("./input/api-contracts"),
        alias="API_CONTRACTS_DIR",
    )
    bruno_collections_dir: Path = Field(
        default=Path("./input/bruno"),
        alias="BRUNO_COLLECTIONS_DIR",
    )
    db_connection_profiles_dir: Path = Field(
        default=Path("./input/db-profiles"),
        alias="DB_CONNECTION_PROFILES_DIR",
    )

    git_provider: str = Field(default="azure_repos", alias="GIT_PROVIDER")
    git_remote_name: str = Field(default="origin", alias="GIT_REMOTE_NAME")
    git_base_branch: str = Field(default="main", alias="GIT_BASE_BRANCH")
    git_work_branch_prefix: str = Field(
        default="ai/generated-tests",
        alias="GIT_WORK_BRANCH_PREFIX",
    )
    pr_title_prefix: str = Field(
        default="[AI Test Scripts]",
        alias="PR_TITLE_PREFIX",
    )
    pr_target_reviewers: str | None = Field(
        default=None,
        alias="PR_TARGET_REVIEWERS",
    )

    azure_repos_org_url: str | None = Field(
        default=None,
        alias="AZURE_REPOS_ORG_URL",
    )
    azure_repos_project: str | None = Field(
        default=None,
        alias="AZURE_REPOS_PROJECT",
    )
    azure_repos_repository: str | None = Field(
        default=None,
        alias="AZURE_REPOS_REPOSITORY",
    )
    azure_repos_pat: str | None = Field(
        default=None,
        alias="AZURE_REPOS_PAT",
    )
