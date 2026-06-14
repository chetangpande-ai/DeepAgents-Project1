from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from test_script_generator.adapters.api_evidence import extract_api_evidence
from test_script_generator.adapters.db_evidence import extract_db_evidence
from test_script_generator.adapters.filesystem import write_json, write_text
from test_script_generator.adapters.github_repo import resolve_automation_repo
from test_script_generator.adapters.manual_input import load_test_cases
from test_script_generator.adapters.maven import validate_maven_compile
from test_script_generator.adapters.playwright_codegen import prepare_recording
from test_script_generator.agents.actionability import assess_test_case
from test_script_generator.agents.planner import create_generation_plan
from test_script_generator.agents.reviewer import review_artifacts
from test_script_generator.agents.script_writer import generate_artifacts
from test_script_generator.config import Settings
from test_script_generator.profiles.base import scan_repo
from test_script_generator.reports.markdown import render_markdown_report
from test_script_generator.schemas import GeneratorState


def run_workflow(initial_state: GeneratorState, settings: Settings) -> GeneratorState:
    graph = build_graph(settings)
    result = graph.invoke(initial_state)
    return _coerce_state(result)


def build_graph(settings: Settings):
    workflow = StateGraph(GeneratorState)

    workflow.add_node("load_manual_test_cases", lambda state: _load_manual_test_cases(state))
    workflow.add_node("classify_framework_profile", lambda state: _classify_framework(state, settings))
    workflow.add_node("scan_automation_repo", lambda state: _scan_repo(state, settings))
    workflow.add_node("assess_test_case_actionability", lambda state: _assess(state))
    workflow.add_node(
        "record_missing_web_steps_with_playwright_codegen",
        lambda state: _prepare_web_recordings(state, settings),
    )
    workflow.add_node("merge_recorded_web_steps", lambda state: state)
    workflow.add_node("create_generation_plan", lambda state: _plan(state))
    workflow.add_node("generate_scripts", lambda state: _generate(state))
    workflow.add_node("self_review_artifacts", lambda state: _review(state))
    workflow.add_node("write_artifacts", lambda state: _write_artifacts(state))
    workflow.add_node("validate_with_maven", lambda state: _validate(state, settings))
    workflow.add_node("package_final_report", lambda state: _package(state))
    workflow.add_node("create_pull_request", lambda state: state)

    workflow.set_entry_point("load_manual_test_cases")
    workflow.add_edge("load_manual_test_cases", "classify_framework_profile")
    workflow.add_edge("classify_framework_profile", "scan_automation_repo")
    workflow.add_edge("scan_automation_repo", "assess_test_case_actionability")
    workflow.add_conditional_edges(
        "assess_test_case_actionability",
        _route_after_assessment,
        {
            "record": "record_missing_web_steps_with_playwright_codegen",
            "plan": "create_generation_plan",
            "package": "package_final_report",
        },
    )
    workflow.add_edge("record_missing_web_steps_with_playwright_codegen", "merge_recorded_web_steps")
    workflow.add_edge("merge_recorded_web_steps", "create_generation_plan")
    workflow.add_edge("create_generation_plan", "generate_scripts")
    workflow.add_edge("generate_scripts", "self_review_artifacts")
    workflow.add_edge("self_review_artifacts", "write_artifacts")
    workflow.add_edge("write_artifacts", "validate_with_maven")
    workflow.add_edge("validate_with_maven", "package_final_report")
    workflow.add_conditional_edges(
        "package_final_report",
        lambda state: "pr" if settings.allow_pr_creation else "end",
        {"pr": "create_pull_request", "end": END},
    )
    workflow.add_edge("create_pull_request", END)
    return workflow.compile()


def _load_manual_test_cases(state: GeneratorState) -> dict[str, Any]:
    if state.test_cases:
        return {}
    if not state.input_file:
        raise ValueError("input_file is required.")
    return {"test_cases": load_test_cases(state.input_file)}


def _classify_framework(state: GeneratorState, settings: Settings) -> dict[str, Any]:
    if state.framework_profile:
        return {}
    framework = settings.default_framework_profile
    if framework not in {"java-testng-maven", "java-bdd-maven"}:
        framework = "java-testng-maven"
    return {"framework_profile": framework}


def _scan_repo(state: GeneratorState, settings: Settings) -> dict[str, Any]:
    framework = state.framework_profile or "java-testng-maven"
    repo_path, warnings = resolve_automation_repo(settings)
    profile = scan_repo(repo_path, framework, warnings=warnings)
    return {"repo_profile": profile}


def _assess(state: GeneratorState) -> dict[str, Any]:
    base_dir = state.input_file.parent if state.input_file else Path.cwd()
    assessments = [assess_test_case(test_case, base_dir) for test_case in state.test_cases]
    api_evidence = []
    for test_case in state.test_cases:
        api_item = extract_api_evidence(test_case)
        if api_item is not None:
            api_evidence.append(api_item)

    db_evidence = []
    for test_case in state.test_cases:
        db_item = extract_db_evidence(test_case)
        if db_item is not None:
            db_evidence.append(db_item)
    return {
        "actionability_assessments": assessments,
        "api_evidence": api_evidence,
        "db_evidence": db_evidence,
    }


def _route_after_assessment(state: GeneratorState) -> str:
    assessments = state.actionability_assessments
    if any(item.requires_web_recording for item in assessments):
        return "record"
    if any(item.generation_allowed for item in assessments):
        return "plan"
    return "package"


def _prepare_web_recordings(state: GeneratorState, settings: Settings) -> dict[str, Any]:
    if not settings.playwright_codegen_enabled:
        return {
            "blockers": state.blockers
            + ["Playwright codegen is disabled, but at least one testcase needs recording."]
        }
    run_dir = _require_run_dir(state)
    by_id = {test_case.source_id: test_case for test_case in state.test_cases}
    recordings = list(state.web_recordings)
    blockers = list(state.blockers)
    for assessment in state.actionability_assessments:
        if not assessment.requires_web_recording:
            continue
        try:
            recordings.append(prepare_recording(by_id[assessment.test_case_id], settings, run_dir))
        except ValueError as exc:
            blockers.append(f"{assessment.test_case_id}: {exc}")
    return {"web_recordings": recordings, "blockers": blockers}


def _plan(state: GeneratorState) -> dict[str, Any]:
    return {
        "generation_plan": create_generation_plan(
            state.test_cases,
            state.actionability_assessments,
        )
    }


def _generate(state: GeneratorState) -> dict[str, Any]:
    if not state.framework_profile:
        return {"blockers": state.blockers + ["Framework profile is missing."]}
    artifacts = generate_artifacts(
        state.test_cases,
        state.generation_plan.planned_test_case_ids,
        state.framework_profile,
    )
    return {"artifacts": artifacts}


def _review(state: GeneratorState) -> dict[str, Any]:
    warnings = review_artifacts(state.artifacts)
    return {"blockers": state.blockers + warnings}


def _write_artifacts(state: GeneratorState) -> dict[str, Any]:
    run_dir = _require_run_dir(state)
    write_json(run_dir / "input-test-cases.json", state.test_cases)
    write_json(run_dir / "actionability-assessments.json", state.actionability_assessments)
    write_json(run_dir / "repo-profile.json", state.repo_profile)
    write_json(run_dir / "generation-plan.json", state.generation_plan)
    write_json(run_dir / "generated-artifacts.json", state.artifacts)
    write_json(run_dir / "api-evidence.json", state.api_evidence)
    write_json(run_dir / "db-evidence.json", state.db_evidence)
    write_json(run_dir / "web-recordings.json", state.web_recordings)
    return {}


def _validate(state: GeneratorState, settings: Settings) -> dict[str, Any]:
    repo_path = Path(state.repo_profile.root_path) if state.repo_profile else settings.automation_repo_path
    result = validate_maven_compile(repo_path, dry_run=settings.dry_run)
    return {"validation_result": result}


def _package(state: GeneratorState) -> dict[str, Any]:
    run_dir = _require_run_dir(state)
    report = render_markdown_report(state)
    report_path = run_dir / "final-report.md"
    write_text(report_path, report)
    write_json(run_dir / "final-state.json", state)
    return {"final_report_path": report_path}


def _require_run_dir(state: GeneratorState) -> Path:
    if not state.run_dir:
        raise ValueError("run_dir is required.")
    return state.run_dir


def _coerce_state(value: Any) -> GeneratorState:
    if isinstance(value, GeneratorState):
        return value
    return GeneratorState.model_validate(value)
