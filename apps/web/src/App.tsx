import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  ClipboardList,
  Code2,
  Database,
  FileCheck2,
  FileText,
  GitPullRequest,
  Globe2,
  Loader2,
  Play,
  Server,
  Terminal,
  Upload,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'
import './App.css'

type AutomationLayer = 'ui' | 'api' | 'db'
type FrameworkProfile = 'java-bdd-maven' | 'java-testng-maven'

type TestStep = {
  step_number: number
  action: string
  expected_result: string
}

type StageLog = {
  stage: string
  status: 'complete' | 'warning' | 'blocked' | 'skipped'
  message: string
  timestamp: string
}

type ApprovalNotice = {
  kind: 'clarification' | 'playwright_recording' | 'review' | 'pr'
  severity: 'info' | 'warning' | 'blocked'
  title: string
  message: string
  test_case_id?: string | null
}

type GeneratedArtifact = {
  path: string
  artifact_type: string
  content: string
  related_test_case_ids: string[]
}

type WebRecordingEvidence = {
  test_case_id: string
  app_url: string
  recording_script_path: string
  notes_path?: string | null
  storage_state_path?: string | null
  generated_locator_candidates: string[]
  command: string[]
}

type RepositoryPublishResult = {
  status:
    | 'skipped'
    | 'prepared'
    | 'pushed'
    | 'initialized'
    | 'pr_created'
    | 'failed'
    | 'no_changes'
  provider: string
  repository?: string | null
  repo_path?: string | null
  branch_name?: string | null
  base_branch?: string | null
  commit_sha?: string | null
  pull_request_url?: string | null
  written_paths: string[]
  initializes_empty_repository: boolean
  message: string
  errors: string[]
}

type GenerateResponse = {
  run_dir: string
  report_path: string | null
  report_markdown: string
  framework_profile: FrameworkProfile
  logs: StageLog[]
  approvals: ApprovalNotice[]
  web_recordings: WebRecordingEvidence[]
  generated_artifacts: GeneratedArtifact[]
  validation_result?: {
    passed: boolean
    skipped: boolean
    errors: string[]
  } | null
  publish_result?: RepositoryPublishResult | null
}

type GenerateRequestBody = {
  framework_profile: FrameworkProfile
  automation_repo_path?: string | null
  dry_run?: boolean | null
  test_case: Record<string, unknown>
}

type FormState = {
  sourceId: string
  title: string
  description: string
  framework: FrameworkProfile
  layers: AutomationLayer[]
  webAppUrl: string
  webRecordMissingSteps: boolean
  webRecordingScriptPath: string
  apiEndpoint: string
  apiMethod: string
  apiPayload: string
  apiExpectedStatus: string
  apiValidationPoints: string
  dbConnectionProfile: string
  dbQuery: string
  dbValidationPoints: string
  steps: TestStep[]
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001'

const defaultForm: FormState = {
  sourceId: 'TC_MANUAL_001',
  title: 'Validate invalid coupon during checkout',
  description: 'Manual tester enters testcase details and lets the generator assess automation readiness.',
  framework: 'java-bdd-maven',
  layers: ['ui'],
  webAppUrl: 'https://test.example.com',
  webRecordMissingSteps: true,
  webRecordingScriptPath: '',
  apiEndpoint: '/api/orders',
  apiMethod: 'POST',
  apiPayload: '{\n  "couponCode": "INVALID"\n}',
  apiExpectedStatus: '400',
  apiValidationPoints: 'error.code == INVALID_COUPON',
  dbConnectionProfile: 'orders-readonly',
  dbQuery: 'select status from orders where correlation_id = :correlationId',
  dbValidationPoints: 'no submitted order exists\nstatus is not SUBMITTED',
  steps: [
    {
      step_number: 1,
      action: 'Log in as a valid customer.',
      expected_result: 'Customer lands on the account home page.',
    },
    {
      step_number: 2,
      action: 'Navigate to checkout and apply an invalid coupon.',
      expected_result: 'Invalid coupon error is displayed.',
    },
    {
      step_number: 3,
      action: 'Submit checkout.',
      expected_result: 'Order is not submitted.',
    },
  ],
}

const defaultJsonText = JSON.stringify(
  {
    framework_profile: 'java-bdd-maven',
    test_case: {
      source_id: 'TC_API_001',
      title: 'Create order API rejects invalid coupon',
      automation_layers: ['api'],
      api: {
        endpoint: '/api/orders',
        method: 'POST',
        request_payload: {
          couponCode: 'INVALID',
        },
        expected_status: 400,
        expected_response_points: ['error.code == INVALID_COUPON'],
      },
      steps: [
        {
          step_number: 1,
          action: 'Submit create order API request with invalid coupon.',
          expected_result: 'API returns invalid coupon error.',
        },
      ],
    },
  },
  null,
  2,
)

function App() {
  const [form, setForm] = useState<FormState>(defaultForm)
  const [inputMode, setInputMode] = useState<'form' | 'json'>('form')
  const [jsonText, setJsonText] = useState(defaultJsonText)
  const [jsonStatus, setJsonStatus] = useState<string | null>(null)
  const [response, setResponse] = useState<GenerateResponse | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeOutput, setActiveOutput] = useState<'artifacts' | 'report'>('artifacts')
  const [recordingMessages, setRecordingMessages] = useState<Record<string, string>>({})

  const layers = new Set(form.layers)
  const statusSummary = useMemo(() => summarize(response), [response])

  async function submit(targetForm = form) {
    await submitRequest(buildRequest(targetForm))
  }

  async function submitJson() {
    try {
      const request = parseJsonRequest(jsonText, form.framework)
      setJsonStatus(`Ready to generate ${String(request.test_case.source_id)}.`)
      await submitRequest(request)
    } catch (caught) {
      setJsonStatus(caught instanceof Error ? caught.message : 'JSON input is invalid.')
    }
  }

  async function submitRequest(requestBody: GenerateRequestBody) {
    setIsRunning(true)
    setError(null)
    setResponse(null)
    try {
      const result = await fetch(`${API_BASE_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      })
      if (!result.ok) {
        const text = await result.text()
        throw new Error(text || `Request failed with ${result.status}`)
      }
      setResponse((await result.json()) as GenerateResponse)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to run generator.')
    } finally {
      setIsRunning(false)
    }
  }

  function importJsonToForm() {
    try {
      const request = parseJsonRequest(jsonText, form.framework)
      setForm(jsonRequestToFormState(request))
      setJsonStatus(`Loaded ${String(request.test_case.source_id)} into the form.`)
      setInputMode('form')
    } catch (caught) {
      setJsonStatus(caught instanceof Error ? caught.message : 'JSON input is invalid.')
    }
  }

  async function uploadJsonFile(file: File | null) {
    if (!file) {
      return
    }
    const text = await file.text()
    setJsonText(text)
    setJsonStatus(`Loaded ${file.name}.`)
  }

  async function startRecording(recording: WebRecordingEvidence) {
    const key = recordingKey(recording)
    setRecordingMessages((current) => ({
      ...current,
      [key]: 'Starting Playwright recorder...',
    }))
    try {
      const result = await fetch(`${API_BASE_URL}/api/recordings/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: recording.command }),
      })
      const body = await result.json()
      if (!result.ok) {
        throw new Error(body.detail || `Recorder launch failed with ${result.status}`)
      }
      setRecordingMessages((current) => ({
        ...current,
        [key]: `${body.message} PID: ${body.pid}`,
      }))
    } catch (caught) {
      setRecordingMessages((current) => ({
        ...current,
        [key]: caught instanceof Error ? caught.message : 'Unable to start recorder.',
      }))
    }
  }

  async function copyRecordingCommand(recording: WebRecordingEvidence) {
    const key = recordingKey(recording)
    try {
      await navigator.clipboard.writeText(recording.command.join(' '))
      setRecordingMessages((current) => ({ ...current, [key]: 'Command copied.' }))
    } catch {
      setRecordingMessages((current) => ({
        ...current,
        [key]: 'Copy failed. Select the command text and copy it manually.',
      }))
    }
  }

  function useRecordingAndGenerate(recording: WebRecordingEvidence) {
    const nextForm = {
      ...form,
      webRecordMissingSteps: false,
      webRecordingScriptPath: recording.recording_script_path,
    }
    setForm(nextForm)
    void submit(nextForm)
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Manual tester workspace</p>
          <h1>Test Script Automation Assistant</h1>
        </div>
        <div className="status-strip" aria-label="Run status summary">
          <SummaryPill label="Ready" value={statusSummary.ready} />
          <SummaryPill label="Blocked" value={statusSummary.blocked} />
          <SummaryPill label="Needs approval" value={statusSummary.approvals} />
        </div>
      </section>

      <section className="workspace-grid">
        <section className="input-panel" aria-label="Testcase input">
          <div className="input-mode-row" role="tablist" aria-label="Input mode">
            <button
              type="button"
              className={inputMode === 'form' ? 'mode-tab active' : 'mode-tab'}
              onClick={() => setInputMode('form')}
            >
              Form
            </button>
            <button
              type="button"
              className={inputMode === 'json' ? 'mode-tab active' : 'mode-tab'}
              onClick={() => setInputMode('json')}
            >
              JSON
            </button>
          </div>

          {inputMode === 'form' ? (
            <FormInput
              addStep={addStep}
              form={form}
              isRunning={isRunning}
              layers={layers}
              removeStep={removeStep}
              submit={() => void submit()}
              toggleLayer={toggleLayer}
              update={update}
              updateStep={updateStep}
            />
          ) : (
            <JsonInput
              importToForm={importJsonToForm}
              isRunning={isRunning}
              jsonStatus={jsonStatus}
              jsonText={jsonText}
              setJsonText={setJsonText}
              submitJson={() => void submitJson()}
              uploadJsonFile={(file) => void uploadJsonFile(file)}
            />
          )}
          {error && <div className="error-box">{error}</div>}
        </section>

        <section className="result-panel" aria-label="Generator results">
          <div className="panel-split">
            <section className="result-section">
              <SectionTitle icon={<CheckCircle2 size={18} />} title="Flow Logs" />
              <div className="timeline">
                {response?.logs.length ? (
                  response.logs.map((log) => <LogItem key={`${log.stage}-${log.timestamp}`} log={log} />)
                ) : (
                  <EmptyState text="Run the generator to see stage-by-stage logs." />
                )}
              </div>
            </section>

            <section className="result-section">
              <SectionTitle icon={<AlertTriangle size={18} />} title="Approvals and Notifications" />
              <div className="notice-list">
                {response?.approvals.length ? (
                  response.approvals.map((notice, index) => (
                    <NoticeItem key={`${notice.kind}-${index}`} notice={notice} />
                  ))
                ) : (
                  <EmptyState text="Approval prompts will appear here when clarification, recording, or review is needed." />
                )}
              </div>
            </section>
          </div>

          <RecordingTasks
            messages={recordingMessages}
            onCopy={(recording) => void copyRecordingCommand(recording)}
            onGenerate={useRecordingAndGenerate}
            onStart={(recording) => void startRecording(recording)}
            recordings={response?.web_recordings ?? []}
          />

          <PublishResult publishResult={response?.publish_result ?? null} />

          <section className="output-panel">
            <div className="output-header">
              <SectionTitle icon={<Code2 size={18} />} title="Generated Output" />
              <div className="tab-row" role="tablist">
                <button
                  type="button"
                  className={activeOutput === 'artifacts' ? 'tab active' : 'tab'}
                  onClick={() => setActiveOutput('artifacts')}
                >
                  Artifacts
                </button>
                <button
                  type="button"
                  className={activeOutput === 'report' ? 'tab active' : 'tab'}
                  onClick={() => setActiveOutput('report')}
                >
                  Report
                </button>
              </div>
            </div>
            {activeOutput === 'artifacts' ? (
              <ArtifactViewer artifacts={response?.generated_artifacts ?? []} />
            ) : (
              <pre className="report-viewer">{response?.report_markdown ?? 'No report yet.'}</pre>
            )}
          </section>

          {response?.run_dir && (
            <div className="run-footer">
              <GitPullRequest size={17} />
              Run artifacts saved at <code>{response.run_dir}</code>
            </div>
          )}
        </section>
      </section>
    </main>
  )

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleLayer(layer: AutomationLayer) {
    setForm((current) => {
      const next = current.layers.includes(layer)
        ? current.layers.filter((item) => item !== layer)
        : [...current.layers, layer]
      return { ...current, layers: next.length ? next : current.layers }
    })
  }

  function updateStep(index: number, key: keyof TestStep, value: string) {
    setForm((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) =>
        stepIndex === index ? { ...step, [key]: key === 'step_number' ? Number(value) : value } : step,
      ),
    }))
  }

  function addStep() {
    setForm((current) => ({
      ...current,
      steps: [
        ...current.steps,
        {
          step_number: current.steps.length + 1,
          action: '',
          expected_result: '',
        },
      ],
    }))
  }

  function removeStep(index: number) {
    setForm((current) => ({
      ...current,
      steps: current.steps
        .filter((_, stepIndex) => stepIndex !== index)
        .map((step, stepIndex) => ({ ...step, step_number: stepIndex + 1 })),
    }))
  }
}

function buildRequest(form: FormState) {
  const testCase = buildTestCaseFromForm(form)

  return {
    framework_profile: form.framework,
    test_case: testCase,
  }
}

function FormInput({
  addStep,
  form,
  isRunning,
  layers,
  removeStep,
  submit,
  toggleLayer,
  update,
  updateStep,
}: {
  addStep: () => void
  form: FormState
  isRunning: boolean
  layers: Set<AutomationLayer>
  removeStep: (index: number) => void
  submit: () => void
  toggleLayer: (layer: AutomationLayer) => void
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void
  updateStep: (index: number, key: keyof TestStep, value: string) => void
}) {
  return (
    <>
      <SectionTitle icon={<ClipboardList size={18} />} title="Testcase Details" />
      <div className="field-grid two">
        <label>
          Testcase ID
          <input value={form.sourceId} onChange={(event) => update('sourceId', event.target.value)} />
        </label>
        <label>
          Framework
          <select
            value={form.framework}
            onChange={(event) => update('framework', event.target.value as FrameworkProfile)}
          >
            <option value="java-bdd-maven">Cucumber JUnit Maven</option>
            <option value="java-testng-maven">TestNG Maven</option>
          </select>
        </label>
      </div>

      <label>
        Title
        <input value={form.title} onChange={(event) => update('title', event.target.value)} />
      </label>

      <label>
        Description
        <textarea rows={3} value={form.description} onChange={(event) => update('description', event.target.value)} />
      </label>

      <div className="layer-row" aria-label="Automation layers">
        <LayerToggle active={layers.has('ui')} icon={<Globe2 size={16} />} label="Web" onClick={() => toggleLayer('ui')} />
        <LayerToggle active={layers.has('api')} icon={<Server size={16} />} label="API" onClick={() => toggleLayer('api')} />
        <LayerToggle active={layers.has('db')} icon={<Database size={16} />} label="DB" onClick={() => toggleLayer('db')} />
      </div>

      {layers.has('ui') && (
        <EvidenceBlock title="Web Evidence" icon={<Globe2 size={17} />}>
          <label>
            Application URL
            <input
              value={form.webAppUrl}
              onChange={(event) => update('webAppUrl', event.target.value)}
              placeholder="https://test.example.com"
            />
          </label>
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={form.webRecordMissingSteps}
              onChange={(event) => update('webRecordMissingSteps', event.target.checked)}
            />
            Route missing web steps to Playwright codegen
          </label>
          <label>
            Recorded Playwright script path
            <input
              value={form.webRecordingScriptPath}
              onChange={(event) => update('webRecordingScriptPath', event.target.value)}
              placeholder=".tsg-runs/.../recordings/TC_001/playwright-codegen.java"
            />
          </label>
        </EvidenceBlock>
      )}

      {layers.has('api') && (
        <EvidenceBlock title="API Evidence" icon={<Server size={17} />}>
          <div className="field-grid two">
            <label>
              Endpoint
              <input
                value={form.apiEndpoint}
                onChange={(event) => update('apiEndpoint', event.target.value)}
                placeholder="/api/orders"
              />
            </label>
            <label>
              Method
              <select value={form.apiMethod} onChange={(event) => update('apiMethod', event.target.value)}>
                <option>GET</option>
                <option>POST</option>
                <option>PUT</option>
                <option>PATCH</option>
                <option>DELETE</option>
              </select>
            </label>
          </div>
          <label>
            Request payload
            <textarea rows={4} value={form.apiPayload} onChange={(event) => update('apiPayload', event.target.value)} />
          </label>
          <div className="field-grid two">
            <label>
              Expected status
              <input value={form.apiExpectedStatus} onChange={(event) => update('apiExpectedStatus', event.target.value)} />
            </label>
            <label>
              Response validations
              <input
                value={form.apiValidationPoints}
                onChange={(event) => update('apiValidationPoints', event.target.value)}
                placeholder="error.code == INVALID_COUPON"
              />
            </label>
          </div>
        </EvidenceBlock>
      )}

      {layers.has('db') && (
        <EvidenceBlock title="DB Evidence" icon={<Database size={17} />}>
          <label>
            Connection profile
            <input
              value={form.dbConnectionProfile}
              onChange={(event) => update('dbConnectionProfile', event.target.value)}
              placeholder="orders-readonly"
            />
          </label>
          <label>
            Query
            <textarea rows={3} value={form.dbQuery} onChange={(event) => update('dbQuery', event.target.value)} />
          </label>
          <label>
            Validation points
            <textarea
              rows={3}
              value={form.dbValidationPoints}
              onChange={(event) => update('dbValidationPoints', event.target.value)}
            />
          </label>
        </EvidenceBlock>
      )}

      <div className="steps-header">
        <SectionTitle icon={<FileText size={18} />} title="Steps and Expected Results" />
        <button type="button" className="secondary-button" onClick={addStep}>
          Add Step
        </button>
      </div>

      <div className="steps-list">
        {form.steps.map((step, index) => (
          <div className="step-row" key={step.step_number}>
            <span className="step-number">{index + 1}</span>
            <label>
              Action
              <input value={step.action} onChange={(event) => updateStep(index, 'action', event.target.value)} />
            </label>
            <label>
              Expected result
              <input
                value={step.expected_result}
                onChange={(event) => updateStep(index, 'expected_result', event.target.value)}
              />
            </label>
            <button
              type="button"
              className="icon-button"
              title="Remove step"
              onClick={() => removeStep(index)}
              disabled={form.steps.length === 1}
            >
              x
            </button>
          </div>
        ))}
      </div>

      <button type="button" className="primary-button" onClick={submit} disabled={isRunning}>
        {isRunning ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        {isRunning ? 'Running generator' : 'Generate Automation Plan'}
      </button>
    </>
  )
}

function JsonInput({
  importToForm,
  isRunning,
  jsonStatus,
  jsonText,
  setJsonText,
  submitJson,
  uploadJsonFile,
}: {
  importToForm: () => void
  isRunning: boolean
  jsonStatus: string | null
  jsonText: string
  setJsonText: (value: string) => void
  submitJson: () => void
  uploadJsonFile: (file: File | null) => void
}) {
  return (
    <section className="json-input-panel">
      <SectionTitle icon={<Upload size={18} />} title="JSON Testcase Input" />
      <div className="json-actions">
        <label className="file-picker">
          Upload JSON file
          <input
            accept=".json,application/json"
            type="file"
            onChange={(event) => uploadJsonFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button type="button" className="secondary-button" onClick={importToForm}>
          Load into form
        </button>
      </div>
      <label>
        Testcase JSON
        <textarea
          className="json-textarea"
          rows={18}
          value={jsonText}
          onChange={(event) => setJsonText(event.target.value)}
          spellCheck={false}
        />
      </label>
      {jsonStatus && <div className="json-status">{jsonStatus}</div>}
      <button type="button" className="primary-button" onClick={submitJson} disabled={isRunning}>
        {isRunning ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
        {isRunning ? 'Running generator' : 'Generate From JSON'}
      </button>
    </section>
  )
}

function buildTestCaseFromForm(form: FormState) {
  const testCase: Record<string, unknown> = {
    source_id: form.sourceId,
    source_system: 'manual-ui',
    title: form.title,
    description: form.description,
    automation_layers: form.layers,
    steps: form.steps.map((step, index) => ({
      ...step,
      step_number: index + 1,
    })),
  }

  if (form.layers.includes('ui')) {
    testCase.web = {
      record_missing_steps: form.webRecordMissingSteps && !form.webRecordingScriptPath,
      app_url: form.webAppUrl || null,
      recording_script_path: form.webRecordingScriptPath || null,
    }
  }

  if (form.layers.includes('api')) {
    testCase.api = {
      endpoint: form.apiEndpoint || null,
      method: form.apiMethod || null,
      request_payload: parseJson(form.apiPayload),
      expected_status: Number(form.apiExpectedStatus) || null,
      expected_response_points: splitLines(form.apiValidationPoints),
    }
  }

  if (form.layers.includes('db')) {
    testCase.db = {
      connection_profile: form.dbConnectionProfile || null,
      query: form.dbQuery || null,
      validation_points: splitLines(form.dbValidationPoints),
    }
  }

  return testCase
}

function parseJsonRequest(value: string, fallbackFramework: FrameworkProfile): GenerateRequestBody {
  const parsed: unknown = JSON.parse(value)
  const payload = normalizeJsonPayload(parsed)
  const framework = asFramework(payload.framework_profile) ?? fallbackFramework

  return {
    framework_profile: framework,
    automation_repo_path: asOptionalString(payload.automation_repo_path),
    dry_run: typeof payload.dry_run === 'boolean' ? payload.dry_run : undefined,
    test_case: validateJsonTestCase(payload.test_case),
  }
}

function normalizeJsonPayload(value: unknown): Record<string, unknown> & { test_case: unknown } {
  if (!isRecord(value)) {
    throw new Error('JSON root must be an object.')
  }
  if ('test_case' in value) {
    return { ...value, test_case: value.test_case }
  }
  if (Array.isArray(value.test_cases)) {
    const firstCase = value.test_cases.find(isRecord)
    if (!firstCase) {
      throw new Error('test_cases must contain at least one testcase object.')
    }
    return { ...value, test_case: firstCase }
  }
  return { test_case: value }
}

function validateJsonTestCase(value: unknown): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new Error('test_case must be an object.')
  }
  if (!asOptionalString(value.source_id)) {
    throw new Error('test_case.source_id is required.')
  }
  if (!asOptionalString(value.title)) {
    throw new Error('test_case.title is required.')
  }
  if (!Array.isArray(value.steps) || value.steps.length === 0) {
    throw new Error('test_case.steps must contain at least one step.')
  }
  return value
}

function jsonRequestToFormState(request: GenerateRequestBody): FormState {
  const testCase = request.test_case
  const api = isRecord(testCase.api) ? testCase.api : {}
  const db = isRecord(testCase.db) ? testCase.db : {}
  const web = isRecord(testCase.web) ? testCase.web : {}

  return {
    sourceId: asString(testCase.source_id, defaultForm.sourceId),
    title: asString(testCase.title, defaultForm.title),
    description: asString(testCase.description, ''),
    framework: request.framework_profile,
    layers: inferLayers(testCase),
    webAppUrl: asString(web.app_url, ''),
    webRecordMissingSteps: Boolean(web.record_missing_steps),
    webRecordingScriptPath: asString(web.recording_script_path, ''),
    apiEndpoint: asString(api.endpoint, ''),
    apiMethod: asString(api.method, 'POST'),
    apiPayload: stringifyJsonField(api.request_payload),
    apiExpectedStatus: asString(api.expected_status, ''),
    apiValidationPoints: arrayToLines(api.expected_response_points),
    dbConnectionProfile: asString(db.connection_profile, ''),
    dbQuery: asString(db.query, ''),
    dbValidationPoints: arrayToLines(db.validation_points),
    steps: stepsToFormState(testCase.steps),
  }
}

function inferLayers(testCase: Record<string, unknown>): AutomationLayer[] {
  const explicitLayers = Array.isArray(testCase.automation_layers) ? testCase.automation_layers : []
  const layers = new Set<AutomationLayer>()
  for (const layer of explicitLayers) {
    if (layer === 'ui') {
      layers.add('ui')
    }
    if (layer === 'api') {
      layers.add('api')
    }
    if (layer === 'db') {
      layers.add('db')
    }
  }
  if (explicitLayers.includes('hybrid')) {
    if (isRecord(testCase.web)) {
      layers.add('ui')
    }
    if (isRecord(testCase.api)) {
      layers.add('api')
    }
    if (isRecord(testCase.db)) {
      layers.add('db')
    }
  }
  if (!layers.size && isRecord(testCase.web)) {
    layers.add('ui')
  }
  if (!layers.size && isRecord(testCase.api)) {
    layers.add('api')
  }
  if (!layers.size && isRecord(testCase.db)) {
    layers.add('db')
  }
  return layers.size ? Array.from(layers) : ['ui']
}

function stepsToFormState(value: unknown): TestStep[] {
  if (!Array.isArray(value)) {
    return defaultForm.steps
  }
  const steps = value.filter(isRecord).map((step, index) => ({
    step_number: Number(step.step_number) || index + 1,
    action: asString(step.action, ''),
    expected_result: asString(step.expected_result, ''),
  }))
  return steps.length ? steps : defaultForm.steps
}

function arrayToLines(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join('\n')
  }
  return asString(value, '')
}

function stringifyJsonField(value: unknown): string {
  if (value === undefined || value === null) {
    return ''
  }
  if (typeof value === 'string') {
    return value
  }
  return JSON.stringify(value, null, 2)
}

function asFramework(value: unknown): FrameworkProfile | null {
  if (value === 'java-bdd-maven' || value === 'java-testng-maven') {
    return value
  }
  return null
}

function asOptionalString(value: unknown): string | undefined {
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  return undefined
}

function asString(value: unknown, fallback: string): string {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return fallback
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseJson(value: string) {
  try {
    return value.trim() ? JSON.parse(value) : null
  } catch {
    return { raw: value }
  }
}

function splitLines(value: string) {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function summarize(response: GenerateResponse | null) {
  if (!response) {
    return { ready: 0, blocked: 0, approvals: 0 }
  }
  return {
    ready: response.logs.filter((log) => log.status === 'complete').length,
    blocked: response.logs.filter((log) => log.status === 'blocked').length,
    approvals: response.approvals.length,
  }
}

function SummaryPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="summary-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="section-title">
      {icon}
      <h2>{title}</h2>
    </div>
  )
}

function LayerToggle({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button type="button" className={active ? 'layer-toggle active' : 'layer-toggle'} onClick={onClick}>
      {icon}
      {label}
    </button>
  )
}

function EvidenceBlock({
  children,
  icon,
  title,
}: {
  children: ReactNode
  icon: ReactNode
  title: string
}) {
  return (
    <section className="evidence-block">
      <SectionTitle icon={icon} title={title} />
      {children}
    </section>
  )
}

function LogItem({ log }: { log: StageLog }) {
  return (
    <div className={`log-item ${log.status}`}>
      <span className="log-dot" />
      <div>
        <strong>{log.stage}</strong>
        <p>{log.message}</p>
      </div>
    </div>
  )
}

function NoticeItem({ notice }: { notice: ApprovalNotice }) {
  return (
    <div className={`notice ${notice.severity}`}>
      <strong>{notice.title}</strong>
      {notice.test_case_id && <span>{notice.test_case_id}</span>}
      <p>{notice.message}</p>
    </div>
  )
}

function RecordingTasks({
  messages,
  onCopy,
  onGenerate,
  onStart,
  recordings,
}: {
  messages: Record<string, string>
  onCopy: (recording: WebRecordingEvidence) => void
  onGenerate: (recording: WebRecordingEvidence) => void
  onStart: (recording: WebRecordingEvidence) => void
  recordings: WebRecordingEvidence[]
}) {
  if (!recordings.length) {
    return null
  }

  return (
    <section className="recording-panel">
      <SectionTitle icon={<Terminal size={18} />} title="Playwright Recording Tasks" />
      <div className="recording-list">
        {recordings.map((recording) => {
          const key = recordingKey(recording)
          return (
            <article className="recording-card" key={key}>
              <div className="recording-card-header">
                <div>
                  <strong>{recording.test_case_id}</strong>
                  <p>Record the missing web flow, close codegen, then generate with the saved script.</p>
                </div>
                <span>{recording.app_url}</span>
              </div>
              <label>
                Codegen command
                <textarea readOnly rows={3} value={recording.command.join(' ')} />
              </label>
              <div className="recording-path-grid">
                <div>
                  <span>Output script</span>
                  <code>{recording.recording_script_path}</code>
                </div>
                {recording.notes_path && (
                  <div>
                    <span>Notes</span>
                    <code>{recording.notes_path}</code>
                  </div>
                )}
              </div>
              <div className="recording-actions">
                <button type="button" className="secondary-button" onClick={() => onStart(recording)}>
                  <Play size={16} />
                  Start recorder
                </button>
                <button type="button" className="secondary-button" onClick={() => onCopy(recording)}>
                  <Clipboard size={16} />
                  Copy command
                </button>
                <button type="button" className="primary-button small" onClick={() => onGenerate(recording)}>
                  <FileCheck2 size={16} />
                  Generate with recording
                </button>
              </div>
              {messages[key] && <div className="recording-message">{messages[key]}</div>}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function PublishResult({ publishResult }: { publishResult: RepositoryPublishResult | null }) {
  if (!publishResult) {
    return null
  }

  const statusLabel = publishResult.status.replace('_', ' ')
  return (
    <section className={`publish-panel ${publishResult.status}`}>
      <SectionTitle icon={<GitPullRequest size={18} />} title="Repository Publish" />
      <div className="publish-summary">
        <span>{statusLabel}</span>
        <p>{publishResult.message}</p>
      </div>
      <div className="publish-grid">
        <PublishField label="Repository" value={publishResult.repository} />
        <PublishField label="Branch" value={publishResult.branch_name} />
        <PublishField label="Commit" value={publishResult.commit_sha} />
        <PublishField label="Pull request" value={publishResult.pull_request_url} isLink />
      </div>
      {publishResult.written_paths.length > 0 && (
        <div className="written-paths">
          <span>Generated files</span>
          {publishResult.written_paths.map((path) => (
            <code key={path}>{path}</code>
          ))}
        </div>
      )}
      {publishResult.errors.length > 0 && (
        <div className="publish-errors">
          {publishResult.errors.map((error) => (
            <p key={error}>{error}</p>
          ))}
        </div>
      )}
    </section>
  )
}

function PublishField({
  isLink = false,
  label,
  value,
}: {
  isLink?: boolean
  label: string
  value?: string | null
}) {
  return (
    <div>
      <span>{label}</span>
      {isLink && value ? (
        <a href={value} rel="noreferrer" target="_blank">
          {value}
        </a>
      ) : (
        <code>{value || 'not available'}</code>
      )}
    </div>
  )
}

function ArtifactViewer({ artifacts }: { artifacts: GeneratedArtifact[] }) {
  if (!artifacts.length) {
    return <EmptyState text="No generated script artifacts yet. The testcase may need approval or recording first." />
  }
  return (
    <div className="artifact-list">
      {artifacts.map((artifact) => (
        <article className="artifact" key={artifact.path}>
          <div className="artifact-title">
            <strong>{artifact.path}</strong>
            <span>{artifact.artifact_type}</span>
          </div>
          <pre>{artifact.content}</pre>
        </article>
      ))}
    </div>
  )
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>
}

function recordingKey(recording: WebRecordingEvidence) {
  return `${recording.test_case_id}-${recording.recording_script_path}`
}

export default App
