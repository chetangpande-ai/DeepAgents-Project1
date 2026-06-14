import subprocess
from pathlib import Path

from test_script_generator.config import Settings


def resolve_automation_repo(settings: Settings) -> tuple[Path, list[str]]:
    configured_path = settings.automation_repo_path
    if configured_path.exists():
        return configured_path, []

    warnings = [
        f"Configured local automation repo path does not exist: {configured_path}",
    ]
    if not settings.github_owner or not settings.github_repository:
        warnings.append("GitHub owner/repository is not configured, so no remote clone was attempted.")
        return configured_path, warnings

    clone_path = (
        Path(".tsg-work")
        / "repos"
        / settings.github_owner
        / settings.github_repository
    )
    repo_url = f"https://github.com/{settings.github_owner}/{settings.github_repository}.git"
    clone_url = _authenticated_repo_url(settings)

    if clone_path.exists():
        warnings.append(f"Using existing GitHub repo clone: {clone_path}")
        return clone_path, warnings

    clone_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(clone_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip()
        warnings.append(f"GitHub clone failed: {_sanitize(error, settings)}")
        return configured_path, warnings

    warnings.append(f"Cloned GitHub repo for scanning: {repo_url} -> {clone_path}")
    return clone_path, warnings


def _authenticated_repo_url(settings: Settings) -> str:
    if settings.github_owner and settings.github_repository and settings.github_token:
        return (
            "https://x-access-token:"
            f"{settings.github_token}@github.com/{settings.github_owner}/{settings.github_repository}.git"
        )
    return f"https://github.com/{settings.github_owner}/{settings.github_repository}.git"


def _sanitize(value: str, settings: Settings) -> str:
    if settings.github_token:
        return value.replace(settings.github_token, "***")
    return value
