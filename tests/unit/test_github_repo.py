from pathlib import Path

from test_script_generator.adapters.github_repo import resolve_automation_repo
from test_script_generator.config import Settings


def test_existing_automation_repo_path_wins(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, AUTOMATION_REPO_PATH=tmp_path)

    path, warnings = resolve_automation_repo(settings)

    assert path == tmp_path
    assert warnings == []
