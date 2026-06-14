# Test Script Generator

Python/LangGraph starter for generating Java automation scripts from manually supplied test cases.

Current implementation focuses on the safe v1 foundation:

- manual testcase input from JSON/YAML/CSV/Markdown
- `java-testng-maven` and `java-bdd-maven` framework profiles
- actionability gate for vague or underspecified tests
- Playwright codegen recording requests for clear web cases with missing UI steps
- API evidence checks for Swagger/OpenAPI, Bruno, or explicit endpoint/payload details
- DB evidence checks for connection profile, query, query parameters, and validation points
- dry-run reports under `.tsg-runs/`

## Setup

```powershell
uv sync
```

Copy `.env.example` to `.env` and fill values as needed. Mesh API variables are named:

```env
MESH_API_KEY=
MESH_API_URL=
MESH_MODEL=
```

## Run

```powershell
uv run test-script-generator generate --input-file input/test-cases.json --framework java-bdd-maven
```

The command writes a run folder with:

- `final-report.md`
- `actionability-assessments.json`
- `generation-plan.json`
- `web-recordings.json`
- `api-evidence.json`
- `db-evidence.json`
- `generated-artifacts.json`

## Behavior

Vague cases such as `place trade -> trade should be placed successfully` are blocked with clarification questions. The generator does not invent locators, hidden workflow steps, payload fields, DB queries, or assertions.

Clear web cases with missing UI implementation details can be routed to Playwright codegen. The generated recording command and notes are saved in the run folder; recorded output is treated as evidence and must be refactored into the Java automation framework.

API cases are blocked unless Swagger/OpenAPI, Bruno, or explicit endpoint/payload/response evidence exists.

DB cases are blocked unless connection profile or credentials, query or named query, and validation points exist. Raw secrets should stay outside testcase files.

## Validate

```powershell
uv run pytest
uv run ruff check .
```
