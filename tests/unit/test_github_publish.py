from pathlib import Path
import subprocess

from test_script_generator.adapters.github_publish import (
    prepare_generated_artifacts_for_publish,
    push_prepared_artifacts,
)
from test_script_generator.config import Settings
from test_script_generator.schemas import GeneratedArtifact


def test_publish_generated_artifacts_pushes_branch_to_configured_remote(tmp_path: Path) -> None:
    repo_path, remote_path = _create_repo_with_bare_remote(tmp_path)
    settings = Settings(
        _env_file=None,
        dry_run=False,
        allow_repo_writes=True,
        allow_pr_creation=False,
        git_base_branch="main",
        git_remote_name=str(remote_path),
        git_work_branch_prefix="ai/generated-tests",
    )
    artifact = GeneratedArtifact(
        path="src/test/java/generated/TCManualGeneratedTest.java",
        artifact_type="test_class",
        content="package generated;\npublic class TCManualGeneratedTest {}\n",
        related_test_case_ids=["TC_MANUAL_001"],
    )

    prepared = prepare_generated_artifacts_for_publish(
        repo_path,
        [artifact],
        settings,
        ["TC_MANUAL_001"],
    )
    pushed = push_prepared_artifacts(repo_path, prepared, settings, "# Report\n")

    assert pushed.status == "pushed"
    assert pushed.branch_name is not None
    assert pushed.commit_sha is not None
    branches = _git(tmp_path, ["--git-dir", str(remote_path), "branch", "--list"]).stdout
    assert pushed.branch_name in branches


def test_publish_is_skipped_in_dry_run(tmp_path: Path) -> None:
    repo_path, _ = _create_repo_with_bare_remote(tmp_path)
    settings = Settings(_env_file=None, dry_run=True)
    artifact = GeneratedArtifact(
        path="src/test/java/generated/TCManualGeneratedTest.java",
        artifact_type="test_class",
        content="package generated;\npublic class TCManualGeneratedTest {}\n",
        related_test_case_ids=["TC_MANUAL_001"],
    )

    result = prepare_generated_artifacts_for_publish(
        repo_path,
        [artifact],
        settings,
        ["TC_MANUAL_001"],
    )

    assert result.status == "skipped"
    assert "DRY_RUN=true" in result.message


def _create_repo_with_bare_remote(tmp_path: Path) -> tuple[Path, Path]:
    repo_path = tmp_path / "repo"
    remote_path = tmp_path / "remote.git"
    repo_path.mkdir()
    _git(repo_path, ["init"])
    _git(repo_path, ["config", "user.name", "Test User"])
    _git(repo_path, ["config", "user.email", "test@example.com"])
    (repo_path / "README.md").write_text("# Automation Repo\n", encoding="utf-8")
    _git(repo_path, ["add", "README.md"])
    _git(repo_path, ["commit", "-m", "Initial commit"])
    _git(repo_path, ["branch", "-M", "main"])
    _git(tmp_path, ["init", "--bare", str(remote_path)])
    _git(repo_path, ["remote", "add", "origin", str(remote_path)])
    _git(repo_path, ["push", "origin", "main"])
    return repo_path, remote_path


def _git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed
