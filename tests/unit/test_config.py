from test_script_generator.config import Settings


def test_github_is_default_git_provider() -> None:
    settings = Settings(_env_file=None)

    assert settings.git_provider == "github"
    assert settings.github_api_url == "https://api.github.com"


def test_blank_playwright_storage_state_path_is_none() -> None:
    settings = Settings(_env_file=None, PLAYWRIGHT_STORAGE_STATE_PATH="")

    assert settings.playwright_storage_state_path is None
