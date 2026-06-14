from pathlib import Path
import subprocess

import httpx

from test_script_generator.adapters.git_provider import build_branch_plan
from test_script_generator.config import Settings
from test_script_generator.schemas import GeneratedArtifact, RepositoryPublishResult


def prepare_generated_artifacts_for_publish(
    repo_path: Path,
    artifacts: list[GeneratedArtifact],
    settings: Settings,
    source_ids: list[str],
) -> RepositoryPublishResult:
    repository = _repository_name(settings)
    if not artifacts:
        return RepositoryPublishResult(
            status="skipped",
            repository=repository,
            repo_path=str(repo_path),
            message="No generated artifacts to publish.",
        )
    if settings.dry_run:
        return RepositoryPublishResult(
            status="skipped",
            repository=repository,
            repo_path=str(repo_path),
            message="DRY_RUN=true, so generated artifacts were not written to the configured repository.",
        )
    if not settings.allow_repo_writes:
        return RepositoryPublishResult(
            status="skipped",
            repository=repository,
            repo_path=str(repo_path),
            message="ALLOW_REPO_WRITES=false, so generated artifacts were not written.",
        )
    if settings.git_provider.lower() != "github":
        return RepositoryPublishResult(
            status="failed",
            repository=repository,
            repo_path=str(repo_path),
            message="Only GitHub publishing is currently implemented.",
            errors=[f"Unsupported git provider: {settings.git_provider}"],
        )
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return RepositoryPublishResult(
            status="failed",
            repository=repository,
            repo_path=str(repo_path),
            message="Configured repository path is not a Git checkout.",
            errors=[f"Missing Git checkout: {repo_path}"],
        )

    dirty = _run_git(repo_path, ["status", "--porcelain"], settings)
    if not dirty.ok:
        return _failed(repo_path, settings, "Unable to inspect configured repository.", dirty.error)
    if dirty.stdout.strip():
        return _failed(
            repo_path,
            settings,
            "Configured repository has uncommitted changes; publishing stopped to avoid mixing changes.",
            dirty.stdout.strip(),
        )

    empty_repo = _repository_has_no_commits(repo_path, settings)
    if empty_repo:
        branch_name = settings.git_base_branch
        base_branch = None
        checkout = _prepare_empty_repository_branch(repo_path, branch_name, settings)
        if not checkout.ok:
            return _failed(repo_path, settings, "Unable to initialize the empty configured repository.", checkout.error)
    else:
        branch_plan = build_branch_plan(
            settings.git_work_branch_prefix,
            source_ids,
            settings.git_base_branch,
            settings.git_remote_name,
        )
        branch_name = branch_plan.work_branch
        base_branch = branch_plan.base_branch
        fetch = _run_git(repo_path, ["fetch", _remote_fetch_url(settings), settings.git_base_branch], settings)
        if not fetch.ok:
            return _failed(repo_path, settings, "Unable to fetch the configured base branch.", fetch.error)

        checkout = _run_git(repo_path, ["checkout", "-B", branch_name, "FETCH_HEAD"], settings)
        if not checkout.ok:
            return _failed(repo_path, settings, "Unable to create generation branch.", checkout.error)

    try:
        written_paths = _write_artifacts(repo_path, artifacts)
    except ValueError as exc:
        return _failed(repo_path, settings, "Generated artifact path is unsafe.", str(exc))

    status = _run_git(repo_path, ["status", "--porcelain", "--", *written_paths], settings)
    if not status.ok:
        return _failed(repo_path, settings, "Unable to inspect generated artifact changes.", status.error)
    if not status.stdout.strip():
        return RepositoryPublishResult(
            status="no_changes",
            repository=repository,
            repo_path=str(repo_path),
            branch_name=branch_name,
            base_branch=base_branch,
            initializes_empty_repository=empty_repo,
            written_paths=written_paths,
            message="Generated artifacts matched the repository contents; no commit was created.",
        )

    return RepositoryPublishResult(
        status="prepared",
        repository=repository,
        repo_path=str(repo_path),
        branch_name=branch_name,
        base_branch=base_branch,
        initializes_empty_repository=empty_repo,
        written_paths=written_paths,
        message=(
            "Generated artifacts were written to initialize the empty configured repository."
            if empty_repo
            else "Generated artifacts were written to the configured repository branch."
        ),
    )


def push_prepared_artifacts(
    repo_path: Path,
    publish_result: RepositoryPublishResult | None,
    settings: Settings,
    report_markdown: str,
) -> RepositoryPublishResult:
    if publish_result is None:
        return RepositoryPublishResult(
            status="skipped",
            repository=_repository_name(settings),
            repo_path=str(repo_path),
            message="Repository publish was not prepared.",
        )
    if publish_result.status != "prepared":
        return publish_result
    if not publish_result.branch_name:
        return publish_result.model_copy(
            update={
                "status": "failed",
                "message": "Repository publish branch is missing.",
                "errors": publish_result.errors + ["Repository publish branch is missing."],
            }
        )

    _run_git(repo_path, ["config", "user.name", "Test Script Generator"], settings)
    _run_git(repo_path, ["config", "user.email", "test-script-generator@local"], settings)

    add = _run_git(repo_path, ["add", "--", *publish_result.written_paths], settings)
    if not add.ok:
        return _copy_failed(publish_result, "Unable to stage generated artifacts.", add.error)

    source_label = ", ".join(_source_ids_from_paths(publish_result.written_paths)) or "manual test cases"
    commit = _run_git(repo_path, ["commit", "-m", f"Add generated test scripts for {source_label}"], settings)
    if not commit.ok:
        return _copy_failed(publish_result, "Unable to commit generated artifacts.", commit.error)

    sha = _run_git(repo_path, ["rev-parse", "HEAD"], settings)
    commit_sha = sha.stdout.strip() if sha.ok else None
    push = _run_git(
        repo_path,
        [
            "push",
            _remote_push_url(settings),
            f"{publish_result.branch_name}:{publish_result.branch_name}",
        ],
        settings,
    )
    if not push.ok:
        return _copy_failed(publish_result, "Unable to push generated artifacts.", push.error)

    pushed = publish_result.model_copy(
        update={
            "status": "initialized" if publish_result.initializes_empty_repository else "pushed",
            "commit_sha": commit_sha,
            "message": (
                "Generated artifacts initialized the empty configured GitHub repository."
                if publish_result.initializes_empty_repository
                else "Generated artifacts were pushed to the configured GitHub repository."
            ),
        }
    )
    if publish_result.initializes_empty_repository:
        return pushed
    if not settings.allow_pr_creation:
        return pushed

    return _create_pull_request(pushed, settings, report_markdown)


def _create_pull_request(
    publish_result: RepositoryPublishResult,
    settings: Settings,
    report_markdown: str,
) -> RepositoryPublishResult:
    if not settings.github_owner or not settings.github_repository:
        return _copy_failed(
            publish_result,
            "Unable to create pull request.",
            "GITHUB_OWNER and GITHUB_REPOSITORY must be configured.",
        )
    if not settings.github_token:
        return _copy_failed(
            publish_result,
            "Unable to create pull request.",
            "GITHUB_TOKEN must be configured.",
        )

    title = f"{settings.pr_title_prefix} {publish_result.branch_name}"
    url = (
        f"{settings.github_api_url.rstrip('/')}/repos/"
        f"{settings.github_owner}/{settings.github_repository}/pulls"
    )
    response = httpx.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "title": title,
            "head": publish_result.branch_name,
            "base": publish_result.base_branch or settings.git_base_branch,
            "body": report_markdown,
        },
        timeout=30,
    )
    if response.status_code not in {200, 201}:
        return _copy_failed(
            publish_result,
            "Generated artifacts were pushed, but pull request creation failed.",
            _sanitize(response.text, settings),
        )

    payload = response.json()
    return publish_result.model_copy(
        update={
            "status": "pr_created",
            "pull_request_url": payload.get("html_url"),
            "message": "Generated artifacts were pushed and a pull request was created.",
        }
    )


def _write_artifacts(repo_path: Path, artifacts: list[GeneratedArtifact]) -> list[str]:
    written_paths: list[str] = []
    root = repo_path.resolve()
    for artifact in artifacts:
        relative_path = _safe_relative_path(artifact.path)
        target_path = (repo_path / relative_path).resolve()
        if root != target_path and root not in target_path.parents:
            raise ValueError(f"Generated artifact path escapes repository: {artifact.path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(artifact.content, encoding="utf-8")
        written_paths.append(relative_path.as_posix())
    return written_paths


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(f"Generated artifact path must be relative: {value}")
    return path


def _source_ids_from_paths(paths: list[str]) -> list[str]:
    source_ids: list[str] = []
    for path in paths:
        for part in Path(path).parts:
            if part.upper().startswith("TC_"):
                source_ids.append(part.rsplit(".", 1)[0])
                break
    return source_ids[:3]


def _remote_fetch_url(settings: Settings) -> str:
    if settings.github_owner and settings.github_repository:
        return f"https://github.com/{settings.github_owner}/{settings.github_repository}.git"
    return settings.git_remote_name


def _repository_has_no_commits(repo_path: Path, settings: Settings) -> bool:
    head = _run_git(repo_path, ["rev-parse", "--verify", "HEAD"], settings)
    return not head.ok


def _prepare_empty_repository_branch(repo_path: Path, branch_name: str, settings: Settings) -> "_GitResult":
    checkout = _run_git(repo_path, ["checkout", "--orphan", branch_name], settings)
    if checkout.ok:
        return checkout
    return _run_git(repo_path, ["switch", "--orphan", branch_name], settings)


def _remote_push_url(settings: Settings) -> str:
    if settings.github_owner and settings.github_repository and settings.github_token:
        return (
            "https://x-access-token:"
            f"{settings.github_token}@github.com/{settings.github_owner}/{settings.github_repository}.git"
        )
    if settings.github_owner and settings.github_repository:
        return f"https://github.com/{settings.github_owner}/{settings.github_repository}.git"
    return settings.git_remote_name


def _repository_name(settings: Settings) -> str | None:
    if settings.github_owner and settings.github_repository:
        return f"{settings.github_owner}/{settings.github_repository}"
    return None


def _failed(
    repo_path: Path,
    settings: Settings,
    message: str,
    error: str,
) -> RepositoryPublishResult:
    return RepositoryPublishResult(
        status="failed",
        repository=_repository_name(settings),
        repo_path=str(repo_path),
        message=message,
        errors=[_sanitize(error, settings)],
    )


def _copy_failed(
    publish_result: RepositoryPublishResult,
    message: str,
    error: str,
) -> RepositoryPublishResult:
    return publish_result.model_copy(
        update={
            "status": "failed",
            "message": message,
            "errors": publish_result.errors + [_sanitize(error, None)],
        }
    )


class _GitResult:
    def __init__(self, returncode: int, stdout: str, stderr: str, settings: Settings | None = None) -> None:
        self.returncode = returncode
        self.stdout = _sanitize(stdout, settings)
        self.stderr = _sanitize(stderr, settings)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def error(self) -> str:
        return self.stderr.strip() or self.stdout.strip() or f"git exited with {self.returncode}"


def _run_git(repo_path: Path, args: list[str], settings: Settings | None = None) -> _GitResult:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=False,
        capture_output=True,
        text=True,
    )
    return _GitResult(completed.returncode, completed.stdout, completed.stderr, settings)


def _sanitize(value: str, settings: Settings | None) -> str:
    sanitized = value
    if settings and settings.github_token:
        sanitized = sanitized.replace(settings.github_token, "***")
    return sanitized
