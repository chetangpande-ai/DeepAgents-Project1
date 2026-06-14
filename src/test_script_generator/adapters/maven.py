import subprocess
from pathlib import Path

from test_script_generator.schemas import ValidationResult


def validate_maven_compile(repo_path: Path, dry_run: bool = True) -> ValidationResult:
    pom_path = repo_path / "pom.xml"
    if not pom_path.exists():
        return ValidationResult(
            passed=False,
            skipped=True,
            errors=[f"No pom.xml found at {pom_path}. Maven validation skipped."],
        )

    command = ["mvn", "-q", "-DskipTests", "test-compile"]
    if dry_run:
        return ValidationResult(
            passed=True,
            skipped=True,
            command=" ".join(command),
            stdout="Dry run: Maven command not executed.",
        )

    completed = subprocess.run(
        command,
        cwd=repo_path,
        check=False,
        capture_output=True,
        text=True,
    )
    return ValidationResult(
        passed=completed.returncode == 0,
        command=" ".join(command),
        stdout=completed.stdout,
        stderr=completed.stderr,
        errors=[] if completed.returncode == 0 else ["Maven compile validation failed."],
    )
