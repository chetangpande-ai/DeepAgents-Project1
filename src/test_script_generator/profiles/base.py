from pathlib import Path

from typing import cast

from test_script_generator.schemas import FrameworkProfile, RepoProfile


def scan_repo(repo_path: Path, default_framework: str) -> RepoProfile:
    framework = _detect_framework(repo_path, default_framework)
    pom = repo_path / "pom.xml"
    warnings: list[str] = []
    if not repo_path.exists():
        warnings.append(f"Automation repo path does not exist: {repo_path}")

    return RepoProfile(
        root_path=str(repo_path),
        framework_profile=framework,
        pom_path=str(pom) if pom.exists() else None,
        test_source_roots=_existing(repo_path, ["src/test/java"]),
        resource_roots=_existing(repo_path, ["src/test/resources", "src/test/resources/features"]),
        package_conventions=_discover_packages(repo_path),
        existing_helpers=_find_by_name(repo_path, ["*BaseTest*.java", "*Helper*.java", "*Util*.java"]),
        existing_page_objects=_find_by_name(repo_path, ["*Page.java", "*PageObject.java"]),
        existing_api_clients=_find_by_name(repo_path, ["*Client.java", "*Api.java", "*Service.java"]),
        existing_db_utilities=_find_by_name(repo_path, ["*Db*.java", "*Database*.java", "*Jdbc*.java"]),
        existing_step_definitions=_find_by_name(repo_path, ["*Steps.java", "*StepDefinitions.java"]),
        warnings=warnings,
    )


def _detect_framework(repo_path: Path, default_framework: str) -> FrameworkProfile:
    pom = repo_path / "pom.xml"
    text = pom.read_text(encoding="utf-8", errors="ignore").lower() if pom.exists() else ""
    if "cucumber-junit" in text or "cucumber-junit-platform-engine" in text:
        return "java-bdd-maven"
    if "testng" in text:
        return "java-testng-maven"
    if default_framework in {"java-testng-maven", "java-bdd-maven"}:
        return cast(FrameworkProfile, default_framework)
    return "java-testng-maven"


def _existing(root: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (root / path).exists()]


def _find_by_name(root: Path, patterns: list[str], limit: int = 30) -> list[str]:
    if not root.exists():
        return []
    found: list[str] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if len(found) >= limit:
                return found
            if ".git" not in path.parts and path.is_file():
                found.append(str(path.relative_to(root)))
    return found


def _discover_packages(root: Path, limit: int = 20) -> list[str]:
    source_root = root / "src/test/java"
    if not source_root.exists():
        return []
    packages: list[str] = []
    for path in source_root.rglob("*.java"):
        if len(packages) >= limit:
            break
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("package ") and stripped.endswith(";"):
                package = stripped.removeprefix("package ").removesuffix(";")
                if package not in packages:
                    packages.append(package)
                break
    return packages
