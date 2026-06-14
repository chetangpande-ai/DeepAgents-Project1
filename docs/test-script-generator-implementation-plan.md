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
- API automation may require reusable clients, endpoints, headers, schemas, and test data.
- DB validation may require safe read-only queries, connection configuration, and expected data rules.
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
uv add langchain langchain-openai langgraph python-dotenv pydantic pydantic-settings typer rich httpx beautifulsoup4 lxml tenacity
uv add --dev pytest pytest-cov ruff mypy
```

`beautifulsoup4` and `lxml` are included because manually copied Azure DevOps test case steps may arrive as HTML.

## 8. Environment Configuration

Use Mesh API names, not direct OpenAI variable names.

```env
MESH_API_KEY=
MESH_API_URL=
MESH_MODEL=
TSG_TEMPERATURE=0.1

INPUT_TESTCASE_FILE=./input/test-cases.json
AUTOMATION_REPO_PATH=../your-java-automation-repo
DEFAULT_FRAMEWORK_PROFILE=java-testng-maven

DRY_RUN=true
MAX_REPAIR_ATTEMPTS=2
ALLOW_REPO_WRITES=true
ALLOW_PR_CREATION=false

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
  -> create_generation_plan     if at least one test case is ready or partial

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

### 11.4 Script Planner

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

### 11.5 Java TestNG Writer

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

### 11.6 Java BDD Writer

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

### 11.7 Assertion Reviewer

Responsibilities:

- Check that every expected result has an assertion.
- Detect weak assertions such as only checking page load.
- Detect missing negative, boundary, or validation checks.
- Detect hardcoded credentials or unstable waits.

### 11.8 Maven Validator and Repair Agent

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
- If the repository has a locator registry pattern, the agent may reference required locator keys and produce a locator gap report.
- If no locator registry pattern exists, the agent should generate a review report and avoid committing non-runnable locator code unless the team explicitly accepts skeleton generation.

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
- Normalized `SourceTestCase` schema.
- Input validation errors with actionable messages.

Exit criteria:

- Given one manual input file, the CLI writes normalized JSON locally.

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
- UI action generation using existing page objects or UI helpers.
- API validation generation using existing service clients where available.
- DB validation generation using existing read-only DB utilities where available.
- Traceability metadata.
- Test data artifact generation.
- Web locator gap reporting for clear workflows with missing locators.

Exit criteria:

- Given a normalized test case and repo profile, the agent produces planned artifacts with valid paths and code.
- Given a vague web scenario, the agent does not generate placeholder code.

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
4. Mixed UI/API/DB planning rules.
5. TestNG Maven generation.
6. Maven compile validation.
7. BDD Maven generation.
8. Repair loop.
9. Local branch and commit workflow.
10. PR creation against the configured repo.

This order reduces risk because script generation can be tested locally before introducing branch push and PR publishing.

## 19. Remaining Clarifying Questions

These are the remaining decisions needed before implementation starts:

1. Which manual input format should be implemented first: JSON, YAML, Markdown, or CSV?
2. Is the configured repo hosted in Azure Repos, GitHub, Bitbucket, or another Git provider?
3. What are the actual package conventions and folder structure in your Java automation repositories?
4. Do you already have page objects, API clients, DB utilities, test data utilities, or step definition libraries that the agent must reuse?
5. What is the expected output for blocked test cases: clarifying questions in the report, PR comments, a defect, or a backlog task?
6. For DB validation, are generated tests allowed to run read-only queries against test databases, or should DB checks be mocked/stubbed in v1?
7. Should skeleton generation ever be allowed for clear web workflows with missing locators, or should those always stay report-only until locators are available?

## 20. Definition of Done

V1 is complete when:

- The CLI can read one or more manually supplied source test cases.
- The agent can normalize Test Case steps into structured data.
- The agent can scan a Java Maven automation repo.
- The graph can choose `java-testng-maven` or `java-bdd-maven`.
- The graph can classify UI, API, DB, and hybrid automation layers.
- The graph can block vague or underspecified test cases before script generation.
- The agent can generate traceable scripts.
- The agent never invents web locators, hidden workflow steps, payload fields, or assertions.
- A vague case such as `place trade -> trade should be placed successfully` produces a clarification report and no placeholder automation code.
- Maven compile validation runs.
- At least one repair attempt works for common generation errors.
- A final report is created for every run.
- PR creation is controlled by configuration and disabled by default.
