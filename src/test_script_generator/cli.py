from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from test_script_generator.adapters.filesystem import create_run_dir
from test_script_generator.config import Settings
from test_script_generator.graph import run_workflow
from test_script_generator.schemas import GeneratorState

app = typer.Typer(help="Generate Java test scripts from manual testcase input.")
console = Console()


@app.command()
def generate(
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", "-i", help="Manual testcase JSON/YAML/CSV/Markdown file."),
    ] = None,
    framework: Annotated[
        str | None,
        typer.Option("--framework", "-f", help="java-testng-maven or java-bdd-maven."),
    ] = None,
    repo_path: Annotated[
        Path | None,
        typer.Option("--repo-path", help="Automation repository path."),
    ] = None,
    run_dir: Annotated[
        Path | None,
        typer.Option("--run-dir", help="Existing or new run output directory."),
    ] = None,
) -> None:
    settings = Settings()
    if input_file:
        settings.input_testcase_file = input_file
    if repo_path:
        settings.automation_repo_path = repo_path
    if framework:
        settings.default_framework_profile = framework

    output_dir = run_dir or create_run_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    state = GeneratorState(
        input_file=settings.input_testcase_file,
        run_dir=output_dir,
        framework_profile=framework,  # type: ignore[arg-type]
    )
    result = run_workflow(state, settings)

    console.print("[bold green]Run complete[/bold green]")
    console.print(f"Report: {result.final_report_path}")
    console.print(f"Planned: {len(result.generation_plan.planned_test_case_ids)}")
    console.print(f"Blocked: {len(result.generation_plan.blocked_test_case_ids)}")
    console.print(f"Needs recording: {len(result.generation_plan.recording_required_test_case_ids)}")


@app.command("validate-input")
def validate_input(
    input_file: Annotated[
        Path,
        typer.Argument(help="Manual testcase JSON/YAML/CSV/Markdown file."),
    ],
) -> None:
    settings = Settings()
    settings.input_testcase_file = input_file
    output_dir = create_run_dir()
    state = GeneratorState(input_file=settings.input_testcase_file, run_dir=output_dir)
    result = run_workflow(state, settings)
    console.print(f"Input valid. Report: {result.final_report_path}")
