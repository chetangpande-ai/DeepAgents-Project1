from pathlib import Path

from test_script_generator.schemas import ApiEvidence, SourceTestCase


def extract_api_evidence(test_case: SourceTestCase) -> ApiEvidence | None:
    if not test_case.api:
        return None
    api = test_case.api
    return ApiEvidence(
        test_case_id=test_case.source_id,
        swagger_or_openapi_path=api.swagger_or_openapi_path,
        bruno_collection_path=api.bruno_collection_path,
        endpoint=api.endpoint,
        method=api.method,
        request_payload=api.request_payload,
        request_payload_path=api.request_payload_path,
        expected_status=api.expected_status,
        expected_response_points=api.expected_response_points,
    )


def validate_api_evidence(test_case: SourceTestCase, base_dir: Path) -> list[str]:
    if "api" not in set(test_case.automation_layers):
        return []
    if not test_case.api:
        return ["API evidence is missing."]

    api = test_case.api
    missing: list[str] = []

    has_contract = _path_supplied(api.swagger_or_openapi_path) or _path_supplied(
        api.bruno_collection_path
    )
    has_explicit_request = bool(api.endpoint and api.method)
    if not has_contract and not has_explicit_request:
        missing.append("Provide Swagger/OpenAPI, Bruno collection, or endpoint + method.")

    if api.request_payload_path and not _resolve(base_dir, api.request_payload_path).exists():
        missing.append(f"Request payload file does not exist: {api.request_payload_path}")

    if api.swagger_or_openapi_path and not _resolve(
        base_dir, api.swagger_or_openapi_path
    ).exists():
        missing.append(f"Swagger/OpenAPI file does not exist: {api.swagger_or_openapi_path}")

    if api.bruno_collection_path and not _resolve(base_dir, api.bruno_collection_path).exists():
        missing.append(f"Bruno collection path does not exist: {api.bruno_collection_path}")

    if api.expected_status is None:
        missing.append("Expected HTTP status is missing.")

    if not api.expected_response_points:
        missing.append("Expected response validation points are missing.")

    return missing


def _path_supplied(value: str | None) -> bool:
    return bool(value and value.strip())


def _resolve(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path
