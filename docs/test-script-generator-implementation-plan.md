# Test Script Generator Deep Agent - Implementation Plan

## 1. Goal

Build a Python-based Test Script Generator Deep Agent that takes manually provided test cases, usually exported or copied from Azure DevOps Test Case work items, and generates maintainable Java automation scripts for these target frameworks:

- `java-testng-maven`
- `java-bdd-maven`

The agent will use `uv`, Python, LangChain, LangGraph, and a Mesh API LLM provider exposed through an OpenAI-compatible endpoint.

The system should not simply ask an LLM to write code. It should inspect the existing automation repository, understand project conventions, create a generation plan, write scripts, validate them with Maven, repair failures when possible, and raise a pull request against the configured automation repository.

## 2. Recommended Architecture

Use LangGraph as the workflow orchestrator and implement the Test Script Generator as a deep agent inside the graph.

```text
Manual Test Case Input
        |
        v
Load Test Cases
        |
        v
Normalize Test Case Data
        |
        v
Classify Framework and Automation Type
        |
        v
Scan Automation Repository
        |
        v
Test Case Actionability Gate
        |
        +--> Blocked: Clarification Report
        |
        v
Create Script Generation Plan
        |
        v
Generate Java Test Scripts
        |
        v
Self Review and Static Validation
        |
        v
Maven Compile / Targeted Test Run
        |
        +--> Repair Loop, if validation fails
        |
        v
Package Output and Traceability
        |
        v
Create Pull Request
```

LangGraph should control deterministic routing, retries, state, and checkpoints. The deep-agent behavior should appear inside the planning, repository understanding, script generation, review, and repair stages.

## 3. Confirmed Decisions

- BDD stack: Cucumber with JUnit.
- Automation coverage: mixed UI, API, and DB validation.
- Test case source for V1: manual input supplied by the user.
- ADO REST integration for fetching or updating work items: ignored for now.
- Publishing model: raise pull requests against a configured automation repository.
- LLM provider: Mesh API through an OpenAI-compatible endpoint.

## 4. Scope

### In Scope

- Read manually provided test cases from JSON, YAML, Markdown, or CSV.
- Preserve source test case IDs, including ADO Test Case IDs when supplied manually.
- Parse test case fields, including title, steps, expected result, tags, priority, area, iteration, and linked requirement IDs when available.
- Support two framework profiles:
  - Java TestNG with Maven.
  - Java BDD with Maven using Cucumber with JUnit.
- Inspect an existing Java automation repository.
- Generate scripts for mixed UI, API, and DB validation scenarios.
- Generate scripts using existing conventions where possible.
- Generate traceability metadata from source test case ID to script file path.
- Validate generated code using Maven.
- Attempt automated repair for compile or obvious syntax errors.
- Produce a final report.
- Create a branch and raise a pull request against the configured automation repository.

### Out of Scope for V1

- Live ADO fetching and ADO field updates.
- Full browser execution in every environment.
- Complex environment provisioning.
- Unapproved destructive edits to the automation repository.
- Direct commits to protected branches.
- Perfect automation of test cases that lack data, selectors, API contracts, or clear expected results.

## 5. Key Assumptions

- Mesh API exposes an OpenAI-compatible chat completion endpoint.
- The Python agent will use `langchain_openai.ChatOpenAI` with `MESH_API_KEY`, `MESH_API_URL`, and `MESH_MODEL`.
- Manually supplied test cases may still contain ADO-style IDs or copied HTML steps, so the input adapter must normalize HTML into structured steps.
- The Java automation repository already has a Maven structure or a desired target structure.
- BDD means Cucumber feature files plus Java step definitions executed through JUnit.
- UI automation may require page objects, selectors, browser configuration, and stable waits.
- Web automation can use Playwright codegen to record missing implementation steps when the business scenario is clear and app access is available.
- API automation requires Swagger/OpenAPI, Bruno collection, or explicit endpoint/payload/response evidence.
- DB validation requires a connection profile or credentials, query, query parameters, and expected validation points.
- Generated scripts should default to dry-run mode until the PR workflow is verified.

## 6. Proposed Python Project Layout

```text
test-script-generator/
  pyproject.toml
  .env.example
  README.md
  docs/
    test-script-generator-implementation-plan.md
  src/
    test_script_generator/
      __init__.py
      cli.py
      config.py
      llm.py
      graph.py
      state.py
      schemas.py
      agents/
        __init__.py
        planner.py
        script_writer.py
        reviewer.py
        repair.py
      adapters/
        __init__.py
        manual_input.py
        playwright_codegen.py
        api_evidence.py
        db_evidence.py
        filesystem.py
        maven.py
        git_provider.py
        pr_provider.py
      profiles/
        __init__.py
        base.py
        java_testng_maven.py
        java_bdd_maven.py
      prompts/
        planner.md
        java_testng_writer.md
        java_bdd_writer.md
        reviewer.md
        repair.md
      reports/
        __init__.py
        markdown.py
        json_report.py
  tests/
    unit/
    fixtures/
```

## 7. Bootstrap Commands

```powershell
uv init --app --package --name test-script-generator
uv add langchain langchain-openai langgraph python-dotenv pydantic pydantic-settings typer rich httpx beautifulsoup4 lxml tenacity pyyaml
uv add --dev pytest pytest-cov ruff mypy
```

`beautifulsoup4` and `lxml` are included because manually copied Azure DevOps test case steps may arrive as HTML.
Playwright codegen recording requires a Playwright CLI available to the agent environment, typically through a configured Node.js toolchain.

## 8. Environment Configuration

Use Mesh API names, not direct OpenAI variable names.

```env
MESH_API_KEY=
MESH_API_URL=
MESH_MODEL=
TSG_TEMPERATURE=0.1

INPUT_TESTCASE_FILE=./input/test-cases.json
INPUT_EVIDENCE_DIR=./input/evidence
AUTOMATION_REPO_PATH=../your-java-automation-repo
DEFAULT_FRAMEWORK_PROFILE=java-testng-maven

DRY_RUN=true
MAX_REPAIR_ATTEMPTS=2
ALLOW_REPO_WRITES=true
ALLOW_PR_CREATION=false

PLAYWRIGHT_CODEGEN_ENABLED=true
PLAYWRIGHT_CODEGEN_OUTPUT_DIR=.tsg-runs/recordings
PLAYWRIGHT_APP_BASE_URL=
PLAYWRIGHT_STORAGE_STATE_PATH=

API_CONTRACTS_DIR=./input/api-contracts
BRUNO_COLLECTIONS_DIR=./input/bruno

DB_CONNECTION_PROFILES_DIR=./input/db-profiles

GIT_PROVIDER=azure_repos
GIT_REMOTE_NAME=origin
GIT_BASE_BRANCH=main
GIT_WORK_BRANCH_PREFIX=ai/generated-tests
PR_TITLE_PREFIX=[AI Test Scripts]
PR_TARGET_REVIEWERS=

AZURE_REPOS_ORG_URL=https://dev.azure.com/your-org
AZURE_REPOS_PROJECT=your-project
AZURE_REPOS_REPOSITORY=your-repo
AZURE_REPOS_PAT=
```

Mesh API LLM adapter:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key=settings.mesh_api_key,
    base_url=settings.mesh_api_url,
    model=settings.mesh_model,
    temperature=settings.tsg_temperature,
)
```

## 9. Core State Model

LangGraph should pass one typed state object through the graph.

```python
from typing import Literal
from pydantic import BaseModel, Field

FrameworkProfile = Literal["java-testng-maven", "java-bdd-maven"]
AutomationLayer = Literal["ui", "api", "db", "hybrid"]
ActionabilityStatus = Literal["ready", "partial", "blocked"]

class TestStep(BaseModel):
    step_number: int
    action: str
    expected_result: str | None = None
    test_data: dict[str, str] = Field(default_factory=dict)

class SourceTestCase(BaseModel):
    source_id: str
    source_system: str = "manual"
    title: str
    description: str | None = None
    steps: list[TestStep]
    automation_layers: list[AutomationLayer] = Field(default_factory=list)
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    linked_requirement_ids: list[str] = Field(default_factory=list)
    area_path: str | None = None
    iteration_path: str | None = None
    web: dict | None = None
    api: dict | None = None
    db: dict | None = None

class WebRecordingEvidence(BaseModel):
    test_case_id: str
    app_url: str
    recording_script_path: str
    notes_path: str | None = None
    storage_state_path: str | None = None
    generated_locator_candidates: list[str] = Field(default_factory=list)

class ApiEvidence(BaseModel):
    test_case_id: str
    swagger_or_openapi_path: str | None = None
    bruno_collection_path: str | None = None
    endpoint: str | None = None
    method: str | None = None
    request_payload: dict | None = None
    expected_status: int | None = None
    expected_response_points: list[str] = Field(default_factory=list)

class DbValidationEvidence(BaseModel):
    test_case_id: str
    connection_profile: str
    query: str
    validation_points: list[str]

class RepoProfile(BaseModel):
    root_path: str
    framework_profile: FrameworkProfile
    pom_path: str | None = None
    test_source_roots: list[str] = Field(default_factory=list)
    resource_roots: list[str] = Field(default_factory=list)
    package_conventions: list[str] = Field(default_factory=list)
    existing_helpers: list[str] = Field(default_factory=list)
    existing_page_objects: list[str] = Field(default_factory=list)
    existing_api_clients: list[str] = Field(default_factory=list)
    existing_db_utilities: list[str] = Field(default_factory=list)
    existing_step_definitions: list[str] = Field(default_factory=list)

class GeneratedArtifact(BaseModel):
    path: str
    artifact_type: Literal["test_class", "feature_file", "step_definition", "runner", "test_data", "report"]
    content: str
    related_test_case_ids: list[str]

class ActionabilityAssessment(BaseModel):
    test_case_id: str
    status: ActionabilityStatus
    ambiguity_types: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    generation_allowed: bool = False
    skeleton_allowed: bool = False

class ValidationResult(BaseModel):
    passed: bool
    command: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    errors: list[str] = Field(default_factory=list)

class GeneratorState(BaseModel):
    input_file: str | None = None
    requested_test_case_ids: list[str] = Field(default_factory=list)
    test_cases: list[SourceTestCase] = Field(default_factory=list)
    web_recordings: list[WebRecordingEvidence] = Field(default_factory=list)
    api_evidence: list[ApiEvidence] = Field(default_factory=list)
    db_evidence: list[DbValidationEvidence] = Field(default_factory=list)
    actionability_assessments: list[ActionabilityAssessment] = Field(default_factory=list)
    framework_profile: FrameworkProfile | None = None
    repo_profile: RepoProfile | None = None
    generation_plan: dict = Field(default_factory=dict)
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    validation_result: ValidationResult | None = None
    repair_attempts: int = 0
    blockers: list[str] = Field(default_factory=list)
    final_report_path: str | None = None
```

## 10. LangGraph Workflow

Recommended nodes:

```text
load_config
load_manual_test_cases
normalize_test_cases
classify_framework_profile
scan_automation_repo
assess_test_case_actionability
record_missing_web_steps_with_playwright_codegen
merge_recorded_web_steps
create_generation_plan
generate_scripts
self_review_artifacts
write_artifacts
validate_with_maven
repair_artifacts
package_final_report
create_pull_request
```

Recommended conditional edges:

```text
normalize_test_cases
  -> package_final_report       if required test case fields are missing
  -> classify_framework_profile otherwise

classify_framework_profile
  -> package_final_report       if framework is unsupported
  -> scan_automation_repo       otherwise

scan_automation_repo
  -> assess_test_case_actionability

assess_test_case_actionability
  -> package_final_report       if all requested test cases are blocked
  -> record_missing_web_steps_with_playwright_codegen if web test cases need recordable implementation details
  -> create_generation_plan     if at least one test case is ready or partial

record_missing_web_steps_with_playwright_codegen
  -> merge_recorded_web_steps   if recording artifacts are saved
  -> package_final_report       if recording is cancelled or required app access is missing

merge_recorded_web_steps
  -> create_generation_plan

validate_with_maven
  -> repair_artifacts           if failed and repair_attempts < MAX_REPAIR_ATTEMPTS
  -> package_final_report       if failed and repair_attempts exhausted
  -> package_final_report       if passed

package_final_report
  -> create_pull_request        if ALLOW_PR_CREATION=true and validation passed
  -> END                        otherwise
```

The graph should checkpoint state after major stages so failed runs can resume without re-fetching or regenerating everything.

## 11. Deep Agent Internal Roles

The Test Script Generator should use specialist subagents or role-specific prompt chains.

### 11.1 Framework Profiler

Responsibilities:

- Inspect `pom.xml`.
- Detect TestNG, Cucumber, Selenium, RestAssured, JUnit, custom libraries, and reporting plugins.
- Identify package naming patterns.
- Identify existing test naming conventions.
- Find reusable base classes, fixtures, page objects, API clients, step definitions, hooks, and utilities.
- Find reusable API clients, DB connection helpers, query utilities, and test data loaders for mixed automation.

Output:

```json
{
  "framework_profile": "java-testng-maven",
  "test_source_roots": ["src/test/java"],
  "resource_roots": ["src/test/resources"],
  "base_test_classes": ["com.company.framework.BaseTest"],
  "assertion_libraries": ["org.testng.Assert"],
  "recommended_package": "com.company.tests.checkout"
}
```

### 11.2 Automation Layer Classifier

Responsibilities:

- Classify each test case as `ui`, `api`, `db`, or `hybrid`.
- Identify required automation capabilities for each layer.
- Mark missing selectors, endpoints, schemas, DB tables, or test data as blockers.
- Prefer existing repository utilities over generating new low-level framework code.

Output:

```json
{
  "test_case_id": "12345",
  "automation_layers": ["ui", "api", "db"],
  "required_capabilities": ["browser_login", "order_api_client", "read_only_order_query"],
  "blockers": []
}
```

### 11.3 Test Case Actionability Gate

Responsibilities:

- Decide whether each test case is detailed enough to automate.
- Detect vague one-line flows such as `place trade`, `submit request`, `process transaction`, or `validate record`.
- Detect missing business data, hidden multi-screen workflows, unclear actors, missing setup, missing assertions, and missing environment assumptions.
- Block web automation when the page, action sequence, input values, and success signal cannot be inferred from the test case or existing repo conventions.
- Route clear web scenarios with missing implementation steps to Playwright codegen when recording inputs are available.
- Block API automation unless Swagger/OpenAPI, Bruno, or explicit payload and endpoint information is available.
- Block DB validation unless connection profile, query, and validation points are available.
- Generate clarification questions and minimum required details for blocked cases.
- Allow partial generation only when the executable part is clear and the unclear part can be cleanly isolated.

Blocking rules:

```text
Block script generation if:
- the test case has fewer than 3 actionable steps for a multi-step business workflow
- the action hides a business process behind one verb, such as "place trade"
- required input data is missing, such as instrument, quantity, order type, side, account, or user role
- the expected result is not directly verifiable
- UI screens, API endpoints, or DB validation targets are not identifiable
- an API testcase lacks Swagger/OpenAPI, Bruno collection, or explicit endpoint/payload/response details
- a DB testcase lacks a connection profile, query, query parameters, or validation points
- the agent would need to invent locators, workflow steps, payload fields, or assertions
```

Example blocked assessment for a vague trade test:

```json
{
  "test_case_id": "TC_12345",
  "status": "blocked",
  "generation_allowed": false,
  "skeleton_allowed": false,
  "ambiguity_types": [
    "functional ambiguity",
    "validation ambiguity",
    "test data ambiguity",
    "locator ambiguity"
  ],
  "missing_details": [
    "trade side",
    "instrument",
    "quantity",
    "order type",
    "account",
    "navigation path",
    "confirmation behavior",
    "success assertion"
  ],
  "blocking_questions": [
    "Which trade type should be placed: equity, option, future, forex, or another instrument type?",
    "What instrument or symbol should be used?",
    "What account and user role should place the trade?",
    "Is the order buy, sell, short sell, or cover?",
    "What order type and quantity should be entered?",
    "Which screens are involved in the trading workflow?",
    "What exact signal proves success: order ID, confirmation message, order status, API response, or DB record?"
  ]
}
```

For this case, the agent should produce a clarification report, not a feature file, step definition, page object, or placeholder locator code.

### 11.4 Playwright Codegen Recorder

Used for web test cases when the business scenario is clear but implementation details are missing.

Responsibilities:

- Start a human-assisted Playwright codegen recording session against `PLAYWRIGHT_APP_BASE_URL`.
- Let the tester perform missing UI steps in the browser.
- Save the recorded script, notes, and any locator candidates under the run folder.
- Merge existing manual test case steps with newly recorded UI actions.
- Treat recorded code as evidence, not as final production automation.
- Refactor the recorded flow into the target Java framework style: TestNG class, Cucumber-JUnit step definitions, page objects, and reusable helpers.

Required inputs:

- App URL.
- Test credentials or `PLAYWRIGHT_STORAGE_STATE_PATH`.
- Test data needed to execute the flow.
- Clear enough business intent to know what the tester is recording.

Saved artifacts:

```text
.tsg-runs/<run-id>/recordings/<test-case-id>/
  playwright-codegen.java
  recording-notes.md
  locator-candidates.json
  merged-test-steps.json
```

Rules:

- Do not run codegen for vague cases such as `place trade` unless the missing business flow, trade data, and success criteria are already clarified.
- Do not blindly commit codegen output.
- Prefer existing page objects and step definitions over new ones.
- Use recorded selectors only when they are stable, such as `data-testid`, accessible role/name, stable IDs, or well-known labels.
- Unstable selectors must become locator gaps or review comments.

### 11.5 Script Planner

Responsibilities:

- Map source test case steps to automation steps.
- Identify required setup, test data, assertions, cleanup, and dependencies.
- Decide whether each test case is automatable, partially automatable, or blocked.
- Create the file-level generation plan.
- Plan artifacts only for test cases where `generation_allowed=true`.

Output:

```json
{
  "test_case_id": "12345",
  "automation_status": "automatable",
  "automation_layers": ["ui", "api", "db"],
  "target_files": [
    "src/test/java/com/company/tests/checkout/TC12345CheckoutValidationTest.java"
  ],
  "required_data": ["valid user", "invalid coupon", "order lookup query"],
  "assertions": ["error message is displayed", "order is not submitted"],
  "blockers": []
}
```

### 11.6 Java TestNG Writer

Used when `framework_profile=java-testng-maven`.

Responsibilities:

- Generate Java TestNG classes.
- Use existing base classes and helper methods.
- Add `@Test` methods with meaningful names.
- Add test data using `@DataProvider` or external JSON, depending on repo conventions.
- Add traceability using comments, annotations, or tags.

Example target layout:

```text
src/test/java/com/company/tests/<module>/TC12345CheckoutValidationTest.java
src/test/resources/testdata/<module>/TC12345_checkout_validation.json
```

Suggested TestNG traceability pattern:

```java
/**
 * ADO Test Case: 12345
 * Requirement: 98765
 */
@Test(description = "ADO_TC_12345 - Validate checkout error for invalid coupon")
public void validateCheckoutErrorForInvalidCoupon() {
    // generated steps
}
```

### 11.7 Java BDD Writer

Used when `framework_profile=java-bdd-maven`.

Responsibilities:

- Generate or extend Cucumber feature files.
- Generate missing Java step definitions.
- Reuse existing step definitions when possible.
- Add tags for source test case and requirement traceability.
- Keep scenario names business-readable.

Example target layout:

```text
src/test/resources/features/<module>/checkout_validation.feature
src/test/java/com/company/steps/<module>/CheckoutSteps.java
src/test/java/com/company/runners/<module>/CheckoutRunner.java
src/test/resources/testdata/<module>/TC12345_checkout_validation.json
```

Suggested BDD traceability pattern:

```gherkin
@ADO_TC_12345 @REQ_98765 @checkout @negative
Scenario: Reject checkout when coupon is invalid
  Given the customer has items in the cart
  When the customer applies an invalid coupon
  Then the checkout error message should be displayed
  And the order should not be submitted
```

### 11.8 Assertion Reviewer

Responsibilities:

- Check that every expected result has an assertion.
- Detect weak assertions such as only checking page load.
- Detect missing negative, boundary, or validation checks.
- Detect hardcoded credentials or unstable waits.

### 11.9 Maven Validator and Repair Agent

Responsibilities:

- Run safe Maven validation commands.
- Parse compilation errors.
- Repair import issues, package issues, missing methods, bad feature-step bindings, and naming mismatches.
- Stop after `MAX_REPAIR_ATTEMPTS`.

Recommended commands:

```powershell
mvn -q -DskipTests test-compile
mvn -q -Dtest=TC12345CheckoutValidationTest test
mvn -q -Dcucumber.filter.tags="@ADO_TC_12345" test
```

For V1, prefer compile validation first. Full execution should be optional because it may require environments, browsers, credentials, services, or test data.

## 12. Framework Profiles

### 12.1 `java-testng-maven`

Detection signals:

- `pom.xml` contains `testng`.
- `src/test/java` contains classes with `org.testng.annotations.Test`.
- Maven Surefire or Failsafe is configured.

Generated artifact rules:

- Prefer adding new test classes over modifying existing tests.
- Reuse base classes if detected.
- Reuse page objects and API clients if available.
- Do not create duplicate helper classes unless no suitable helper exists.
- Use `Assert` or the repo's preferred assertion library.
- Add traceability to every generated test method.

Validation:

- `mvn -q -DskipTests test-compile`
- Targeted run if environment-ready:
  - `mvn -q -Dtest=<GeneratedClassName> test`

### 12.2 `java-bdd-maven`

Detection signals:

- `pom.xml` contains `cucumber-java` and either `cucumber-junit` or `cucumber-junit-platform-engine`.
- `src/test/resources/features` exists.
- Java step definition classes contain `io.cucumber.java.en.Given`, `When`, `Then`.
- Test runners use JUnit 4 `@RunWith(Cucumber.class)` or JUnit Platform suite configuration.

Generated artifact rules:

- Prefer adding feature scenarios to the correct module feature file.
- Reuse step definitions when semantic matches exist.
- Generate new step definitions only when reuse confidence is low.
- Keep Gherkin business-readable and avoid UI implementation detail in feature files.
- Add source test case and requirement tags to each scenario.
- Generate JUnit-compatible Cucumber runners only when the repository does not already provide a reusable runner.

Validation:

- `mvn -q -DskipTests test-compile`
- Targeted run if environment-ready:
  - `mvn -q -Dcucumber.filter.tags="@ADO_TC_12345" test`

Confirmed runner:

- Cucumber with JUnit.

## 13. Manual Input and PR Publishing

### 13.1 Manual Input Modes

Support manually supplied test cases first. The user can provide input as:

1. JSON file.
2. YAML file.
3. Markdown table or structured Markdown file.
4. CSV export.

Example CLI commands:

```powershell
uv run test-script-generator generate --input-file input/test-cases.json --framework java-testng-maven
uv run test-script-generator generate --input-file input/test-cases.yaml --framework java-bdd-maven
uv run test-script-generator generate --input-file input/test-cases.md --framework java-bdd-maven --repo-path ../automation-repo
```

### 13.2 Manual Input Contract

Preferred JSON format:

```json
{
  "test_cases": [
    {
      "source_id": "12345",
      "source_system": "ado-manual",
      "title": "Reject checkout when coupon is invalid",
      "description": "Validate UI error, API response, and DB order status.",
      "automation_layers": ["ui", "api", "db"],
      "tags": ["checkout", "negative"],
      "linked_requirement_ids": ["98765"],
      "web": {
        "record_missing_steps": true,
        "app_url": "https://test.example.com",
        "storage_state_path": "./input/evidence/storage/customer-user.json"
      },
      "api": {
        "swagger_or_openapi_path": "./input/api-contracts/orders-openapi.yaml",
        "bruno_collection_path": "./input/bruno/orders",
        "endpoint": "/api/orders",
        "method": "POST",
        "request_payload_path": "./input/evidence/payloads/order-request.json",
        "expected_status": 400,
        "expected_response_points": ["error.code == INVALID_COUPON"]
      },
      "db": {
        "connection_profile": "orders-readonly",
        "query": "select status from orders where correlation_id = :correlationId",
        "validation_points": ["no submitted order exists", "status is not SUBMITTED"]
      },
      "steps": [
        {
          "step_number": 1,
          "action": "Log in as a valid customer and add an item to the cart.",
          "expected_result": "The cart shows the selected item."
        },
        {
          "step_number": 2,
          "action": "Apply an invalid coupon and submit checkout.",
          "expected_result": "The UI shows an invalid coupon error, the order API rejects the request, and no submitted order is stored in DB."
        }
      ]
    }
  ]
}
```

Minimum required fields:

- `source_id`
- `title`
- `steps[].action`
- `steps[].expected_result`

Recommended fields:

- `source_system`
- `description`
- `automation_layers`
- `tags`
- `linked_requirement_ids`
- `priority`
- `area_path`
- `iteration_path`
- `web.record_missing_steps`
- `web.app_url`
- `web.storage_state_path`
- `api.swagger_or_openapi_path`
- `api.bruno_collection_path`
- `api.request_payload_path`
- `api.expected_response_points`
- `db.connection_profile`
- `db.query`
- `db.validation_points`

Layer-specific requirements:

- Web test cases with missing UI steps require Playwright codegen inputs: app URL, credentials or storage state, test data, and clear business intent.
- API test cases require at least one of Swagger/OpenAPI, Bruno collection, or explicit payload and endpoint details.
- DB test cases require a database connection profile or credentials, the query to execute, and validation points.
- Raw DB passwords, tokens, and secrets should not be committed in the testcase file. Use secure env vars or a named connection profile referenced by the testcase.

### 13.3 Pull Request Publishing

The agent should not push directly to the base branch. When PR creation is enabled, it should:

1. Validate the configured automation repository path.
2. Verify the worktree is clean or create a clearly isolated branch from the configured base branch.
3. Create a branch using `GIT_WORK_BRANCH_PREFIX`, for example `ai/generated-tests/12345`.
4. Write generated artifacts into the automation repo.
5. Run Maven validation.
6. Commit only generated or modified files from the run.
7. Push the branch to the configured remote.
8. Create a pull request with the final report as the PR description.

PR description should include:

- Source test case IDs.
- Framework profile.
- Automation layers: UI, API, DB, or hybrid.
- Generated files.
- Validation commands and results.
- Repair attempts.
- Blockers and assumptions.
- Manual review checklist.

### 13.4 Future ADO Integration

ADO REST integration can be added later as a separate adapter. For now:

- Do not fetch ADO work items directly.
- Do not update ADO work items directly.
- Preserve ADO Test Case IDs in `source_id` when the user supplies them manually.

## 14. Script Generation Rules

The agent must follow these rules:

- Use the existing automation repository conventions before inventing new ones.
- Never generate code without traceability to a source test case ID.
- Every expected result must map to at least one assertion.
- Do not hardcode secrets, credentials, tokens, or environment URLs.
- Prefer stable waits and framework utilities over raw sleeps.
- Prefer reusable page objects, service clients, DB utilities, and fixtures.
- Separate test data from test logic when the target repository already follows that pattern.
- Use read-only DB validation unless an explicit test setup or cleanup pattern exists.
- Mark non-automatable or underspecified test cases as blocked instead of hallucinating missing details.
- Generate minimal changes necessary for the requested test cases.
- Keep all generated paths inside the configured automation repository root.

### 14.1 Web Scenario Generation Policy

The agent must distinguish between two different web automation problems.

Problem 1: clear workflow, missing locators.

- Example: the test case clearly says login, navigate to checkout, enter invalid coupon, submit, and verify the error message.
- The agent may generate test intent, feature/scenario structure, step definitions, and page object method names.
- The agent must not invent CSS selectors, XPath, IDs, or labels.
- If missing steps or locators can be captured from the application, the agent should start a Playwright codegen recording session and save the recording artifacts.
- The generation plan should merge the original testcase steps with newly recorded Playwright actions before creating Java automation.
- If the repository has a locator registry pattern, the agent may reference required locator keys and produce a locator gap report.
- If no locator registry pattern exists, the agent should generate a review report and avoid committing non-runnable locator code unless the team explicitly accepts skeleton generation.
- Codegen output must be refactored into the target Java framework; it should not be pasted into the repo as raw generated code.

Problem 2: vague business action, missing workflow and data.

- Example: `place trade` with expected result `trade should be placed successfully`.
- The agent must block script generation.
- The agent must not create placeholder steps such as `clickPlaceTradeButton`, `enterTradeDetails`, or `verifyTradeSuccess` because the number of screens, controls, fields, APIs, and assertions are unknown.
- The agent should produce a clarification report listing missing business details and automation blockers.

For vague web scenarios, the output should look like this:

```text
Automation status: blocked
Reason: insufficient procedural detail and missing trade data

No script generated.
No feature file generated.
No page object generated.
No placeholder locators generated.
```

Minimum clarification questions for `place trade`:

- Which instrument type is in scope: equity, option, future, forex, or another asset class?
- What symbol or instrument should be used?
- What account, user role, and permissions are required?
- Is the trade buy, sell, short sell, or cover?
- What order type, price, quantity, and time-in-force should be entered?
- Which screens or navigation path should be used?
- Is there a preview or confirmation step before submission?
- What proves success: order ID, confirmation message, order book status, API response, DB record, or all of these?

Only after these details are available should the agent generate web automation.

### 14.2 API Scenario Generation Policy

API test cases require concrete interface evidence. The agent can generate API validation code only when at least one of these is available:

- Swagger/OpenAPI contract.
- Bruno collection.
- Explicit endpoint, method, headers, request payload, expected status, and expected response validation points.

The agent should use the evidence in this order:

1. Existing API clients in the automation repo.
2. Bruno collection request definitions.
3. Swagger/OpenAPI operation definitions and schemas.
4. Explicit payload information supplied in the testcase.

Blocking rules:

```text
Block API script generation if:
- endpoint or operation is unknown
- request payload is missing for a request that requires a body
- authentication/header requirements are unknown
- expected status code is missing
- response validation points are missing or vague
- the agent would need to invent payload fields, schema details, or assertions
```

The final report should list missing API evidence, such as contract path, Bruno request name, payload example, auth profile, or response assertions.

### 14.3 DB Validation Generation Policy

DB test cases require explicit database validation evidence. The testcase must provide:

- Database connection profile or secure credential reference.
- Query or named query reference.
- Query parameters or how to derive them from the test flow.
- Validation points.

Credential rule:

- Prefer a named connection profile such as `orders-readonly`.
- Store actual credentials in secure environment variables, secret stores, or local ignored config.
- Do not commit raw DB passwords, tokens, or connection strings into generated scripts, reports, or testcase files.

Blocking rules:

```text
Block DB script generation if:
- connection profile or credentials are missing
- query or named query reference is missing
- query parameters are not derivable
- validation points are missing
- write access is required but no explicit setup/cleanup policy exists
- the agent would need to invent table names, joins, expected rows, or assertions
```

DB validation should default to read-only checks. If setup or cleanup writes are required, they must be explicitly approved and implemented using existing repository patterns.

## 15. Human Approval Gates

Recommended gates:

```text
Gate 1: After generation plan
  Human reviews target files, assumptions, and blockers.

Gate 2: Before writing files
  Human approves planned repository changes if DRY_RUN=false.

Gate 3: Before PR creation
  Human approves branch push and pull request creation.
```

For early V1, Gate 1 and Gate 3 are the most important.

## 16. Output Artifacts

Each run should create a local run folder:

```text
.tsg-runs/
  2026-06-14T10-30-00/
    input-test-cases.json
    input-evidence/
      api-contracts/
      bruno/
      db-profiles/
    recordings/
      <test-case-id>/
        playwright-codegen.java
        recording-notes.md
        locator-candidates.json
        merged-test-steps.json
    actionability-assessments.json
    repo-profile.json
    generation-plan.json
    generated-artifacts.json
    locator-gaps.json
    validation-result.json
    final-report.md
```

Final report should include:

- Source test case IDs processed.
- Framework profile used.
- Automation layers processed: UI, API, DB, or hybrid.
- Actionability status for each test case.
- Playwright recording paths used for web scenarios.
- API evidence used: Swagger/OpenAPI, Bruno, or explicit payload.
- DB evidence used: connection profile, query reference, and validation points.
- Generated file paths.
- Locator gaps, if any.
- Validation commands run.
- Validation result.
- Repair attempts.
- Blockers and clarifying questions.
- Manual-only or partially automatable test cases.
- Pull request status.

## 17. Implementation Phases

### Phase 0 - Decisions and Inputs

Deliverables:

- BDD runner confirmed as Cucumber with JUnit.
- Confirm manual input format for the first implementation, preferably JSON.
- Confirm target automation repo layout.
- Publishing model confirmed as pull requests against the configured repo.
- Confirm PR provider, for example Azure Repos or GitHub.

Exit criteria:

- `.env.example` fields are agreed.
- Framework profile rules are agreed.
- Manual input schema is agreed.
- PR branch naming and base branch are agreed.

### Phase 1 - Python Scaffold

Deliverables:

- `uv` project.
- CLI entrypoint.
- Settings loader.
- Mesh API LLM adapter.
- Basic logging.

Exit criteria:

- `uv run test-script-generator --help` works.
- LLM smoke test works against Mesh API.

### Phase 2 - Manual Input Adapter

Deliverables:

- JSON input parser.
- Optional YAML, Markdown, and CSV parsers.
- Test Case step HTML parser for copied ADO content.
- Web evidence parser for app URL, storage state, and codegen recording preference.
- API evidence parser for Swagger/OpenAPI path, Bruno path, endpoint, payload, expected status, and response validation points.
- DB evidence parser for connection profile, query, query parameters, and validation points.
- Normalized `SourceTestCase` schema.
- Input validation errors with actionable messages.

Exit criteria:

- Given one manual input file, the CLI writes normalized JSON locally.
- API and DB cases without required evidence are flagged before script generation.

### Phase 3 - Automation Repository Scanner

Deliverables:

- Maven project detector.
- TestNG detector.
- BDD/Cucumber detector.
- Existing helper, page object, API client, DB utility, step definition, and package scanner.
- Repo profile JSON.

Exit criteria:

- Given a repo path, the scanner identifies `java-testng-maven` or `java-bdd-maven` and lists relevant conventions.

### Phase 4 - LangGraph Workflow

Deliverables:

- Graph state model.
- Graph nodes.
- Test Case Actionability Gate.
- Conditional routing.
- Repair loop.
- Checkpointing.

Exit criteria:

- A dry run can move from manual input to actionability assessment and generation plan without writing Java files.
- A vague test case such as `place trade -> trade should be placed successfully` is blocked with clarification questions.

### Phase 5 - Script Generation

Deliverables:

- TestNG script writer.
- BDD feature writer.
- Step definition writer.
- UI action generation using existing page objects, UI helpers, and approved Playwright codegen recordings.
- Playwright codegen recording adapter for missing web steps and locator candidates.
- Merge logic for existing testcase steps plus newly recorded web actions.
- API validation generation using Swagger/OpenAPI, Bruno, explicit payloads, and existing service clients where available.
- DB validation generation using secure connection profiles, explicit queries, validation points, and existing read-only DB utilities where available.
- Traceability metadata.
- Test data artifact generation.
- Web locator gap reporting for clear workflows with missing locators.

Exit criteria:

- Given a normalized test case and repo profile, the agent produces planned artifacts with valid paths and code.
- Given a vague web scenario, the agent does not generate placeholder code.
- Given a clear web scenario with missing steps, the agent can save a Playwright recording and use it as generation evidence.
- API scripts are generated only when Swagger/OpenAPI, Bruno, or explicit endpoint/payload/response evidence exists.
- DB validation scripts are generated only when connection profile, query, and validation points exist.

### Phase 6 - Validation and Repair

Deliverables:

- Maven command runner.
- Compile validation.
- Targeted TestNG command.
- Targeted BDD tag command.
- Error parser.
- Repair prompt and bounded repair loop.

Exit criteria:

- The agent can repair simple compile issues such as imports, packages, class names, missing semicolons, and Cucumber binding mismatches.

### Phase 7 - Reporting and PR Publishing

Deliverables:

- JSON report.
- Markdown report.
- Git branch creation.
- Commit creation for generated artifacts.
- PR creation adapter.
- PR description generated from the final report.

Exit criteria:

- Dry-run reports are complete.
- Branch push and PR creation occur only when explicitly enabled.

### Phase 8 - Evaluation Suite

Deliverables:

- Fixture manual test cases.
- Fixture Playwright codegen recordings.
- Fixture Swagger/OpenAPI contracts, Bruno collections, payloads, and DB validation specs.
- Golden output checks.
- Unit tests for parsers and profile detection.
- Regression tests for generated file path safety.
- Evaluation rubric for code quality and assertion quality.

Exit criteria:

- CI can validate core generator behavior without requiring live ADO, live Mesh API, or a real PR provider.

### Phase 9 - Production Hardening

Deliverables:

- Role-based access and credential storage approach.
- Audit logging.
- Retry and rate-limit handling.
- Observability dashboard or run history.
- Approval workflow.
- Prompt/version management.

Exit criteria:

- Runs are auditable, reproducible, and safe for team use.

## 18. MVP Recommendation

Build the MVP in this order:

1. Local dry-run generator from fixture JSON.
2. Automation repo scanner.
3. Test Case Actionability Gate.
4. Evidence validation for web, API, and DB cases.
5. Playwright codegen recording and merge flow for web gaps.
6. Mixed UI/API/DB planning rules.
7. TestNG Maven generation.
8. Maven compile validation.
9. BDD Maven generation.
10. Repair loop.
11. Local branch and commit workflow.
12. PR creation against the configured repo.

This order reduces risk because script generation can be tested locally before introducing branch push and PR publishing.

## 19. Remaining Clarifying Questions

These are the remaining decisions needed before implementation starts:

1. Which manual input format should be implemented first: JSON, YAML, Markdown, or CSV?
2. Is the configured repo hosted in Azure Repos, GitHub, Bitbucket, or another Git provider?
3. What are the actual package conventions and folder structure in your Java automation repositories?
4. Do you already have page objects, API clients, DB utilities, test data utilities, or step definition libraries that the agent must reuse?
5. What is the expected output for blocked test cases: clarifying questions in the report, PR comments, a defect, or a backlog task?
6. Which Playwright codegen command and target should be standardized in your environment?
7. For API tests, should Swagger/OpenAPI, Bruno, or explicit payload files be treated as the preferred source of truth when they disagree?
8. For DB validation, how should connection profiles resolve credentials: local `.env`, CI secrets, Key Vault, or another secret store?
9. Are generated tests allowed to run read-only queries against test databases, or should DB checks be mocked/stubbed in v1?
10. Should skeleton generation ever be allowed for clear web workflows with missing locators, or should those always stay report-only until locators are available?

## 20. Definition of Done

V1 is complete when:

- The CLI can read one or more manually supplied source test cases.
- The agent can normalize Test Case steps into structured data.
- The agent can scan a Java Maven automation repo.
- The graph can choose `java-testng-maven` or `java-bdd-maven`.
- The graph can classify UI, API, DB, and hybrid automation layers.
- The graph can block vague or underspecified test cases before script generation.
- The graph can route clear web cases with missing implementation steps through Playwright codegen recording.
- The agent can generate traceable scripts.
- The agent never invents web locators, hidden workflow steps, payload fields, or assertions.
- A vague case such as `place trade -> trade should be placed successfully` produces a clarification report and no placeholder automation code.
- Web scripts can use existing steps plus saved Playwright recording artifacts as generation evidence.
- API scripts are blocked unless Swagger/OpenAPI, Bruno, or explicit endpoint/payload/response evidence is available.
- DB validation scripts are blocked unless connection profile or credentials, query, and validation points are available.
- Maven compile validation runs.
- At least one repair attempt works for common generation errors.
- A final report is created for every run.
- PR creation is controlled by configuration and disabled by default.
