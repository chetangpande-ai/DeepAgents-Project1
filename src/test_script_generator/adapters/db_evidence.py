from test_script_generator.schemas import DbValidationEvidence, SourceTestCase


def extract_db_evidence(test_case: SourceTestCase) -> DbValidationEvidence | None:
    if not test_case.db:
        return None
    db = test_case.db
    return DbValidationEvidence(
        test_case_id=test_case.source_id,
        connection_profile=db.connection_profile,
        query=db.query,
        named_query=db.named_query,
        query_parameters=db.query_parameters,
        validation_points=db.validation_points,
    )


def validate_db_evidence(test_case: SourceTestCase) -> list[str]:
    if "db" not in set(test_case.automation_layers):
        return []
    if not test_case.db:
        return ["DB validation evidence is missing."]

    db = test_case.db
    missing: list[str] = []
    if not db.connection_profile:
        missing.append("DB connection profile is missing.")
    if not db.query and not db.named_query:
        missing.append("DB query or named query is missing.")
    if not db.validation_points:
        missing.append("DB validation points are missing.")
    return missing
