from test_script_generator.schemas import (
    ActionabilityAssessment,
    GenerationPlan,
    SourceTestCase,
)


def create_generation_plan(
    test_cases: list[SourceTestCase],
    assessments: list[ActionabilityAssessment],
) -> GenerationPlan:
    assessment_by_id = {item.test_case_id: item for item in assessments}
    planned: list[str] = []
    blocked: list[str] = []
    recording: list[str] = []
    notes: list[str] = []

    for test_case in test_cases:
        assessment = assessment_by_id.get(test_case.source_id)
        if not assessment:
            blocked.append(test_case.source_id)
            notes.append(f"{test_case.source_id}: missing actionability assessment.")
            continue
        if assessment.generation_allowed:
            planned.append(test_case.source_id)
        elif assessment.requires_web_recording:
            recording.append(test_case.source_id)
            notes.append(f"{test_case.source_id}: Playwright recording required before script generation.")
        else:
            blocked.append(test_case.source_id)
            notes.append(f"{test_case.source_id}: blocked - {', '.join(assessment.missing_details)}")

    return GenerationPlan(
        planned_test_case_ids=planned,
        blocked_test_case_ids=blocked,
        recording_required_test_case_ids=recording,
        notes=notes,
    )
