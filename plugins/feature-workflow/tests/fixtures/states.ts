// CREW Cockpit 測試 fixture：state.json／verification-ir.json 的原始文字。
//
// 形狀取自真實 CREW 產出（crew-state.py new_state()/normalize() 寫出的欄位與順序、
// plan-verify 8b 的 results.verify 摘要 key、references/verification-ir.md Schema v1），
// 內容改寫為中性 slug。`claude plugin test` 的環境沒有檔案系統，
// 所以 fixture 以「檔案原文字串」放在 .ts 模組，由 tests/fixtures/world.ts 以 fs hook 注入。

const step = (status: string, at: string | null = null, reason: string | null = null) => ({
  status,
  at,
  commit: null,
  reason,
})

const pendingGate = { status: 'pending', at: null, by: null, reason: null }

const emptyWorkUnit = {
  skill: null,
  done: 0,
  total: 0,
  label: '',
  remaining: [],
  evidence: [],
  ambiguities: [],
}

const text = (value: unknown): string => JSON.stringify(value, null, 2)

/**
 * schema v2 feature，phase=verify，驗收 WARN 且 blocked=2（BLOCKED 衍生顯示的原料），
 * work_unit 中斷於 3/5，next 快照故意是 /plan-verify --recheck。
 */
export const V2_FEATURE_VERIFY_WARN_BLOCKED = text({
  schema_version: 2,
  slug: 'push-tag-query',
  name: '推播標籤查詢',
  type: 'feature',
  inferred: false,
  phase: 'verify',
  next: {
    command: '/plan-verify --recheck',
    reason: '驗收有 WARN；可重驗，或確認可接受後改跑 /plan-review',
  },
  steps: {
    start: step('done', '2026-10-01T09:00:00+08:00'),
    spec: step('done', '2026-10-01T10:00:00+08:00'),
    db: step('skipped', '2026-10-01T10:00:00+08:00', 'DB_REQUIRED=false'),
    arch: step('done', '2026-10-01T11:00:00+08:00'),
    build: step('done', '2026-10-02T15:00:00+08:00'),
    security: step('done', '2026-10-02T16:00:00+08:00'),
    verify: step('in_progress', '2026-10-03T09:00:00+08:00'),
    review: step('pending'),
    close: step('pending'),
  },
  work_unit: {
    skill: 'plan-verify',
    done: 3,
    total: 5,
    label: 'browser verification',
    remaining: ['AC-4', 'AC-5'],
    evidence: [],
    ambiguities: [],
  },
  gates: {
    requirement: { status: 'approved', at: '2026-10-01T10:00:00+08:00', by: 'human', reason: 'user approved spec' },
    architecture: { status: 'approved', at: '2026-10-01T11:00:00+08:00', by: 'human', reason: 'user approved arch' },
    uat: pendingGate,
  },
  resume_hint: { branch: 'feature/push-tag-query', services: [], read_first: ['plan.md', 'verify.md'] },
  results: {
    verify: {
      health_score: 82,
      passed: 5,
      failed: 0,
      blocked: 2,
      skipped: 0,
      manual: 0,
      mode: 'full',
      status: 'WARN',
    },
    review: {},
    security: { status: 'PASS', critical: 0, high: 0 },
  },
  git: { branch: 'feature/push-tag-query', base: 'main', last_commit: null },
  notion: { page_id: '00000000-0000-0000-0000-000000000001', mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  history: [
    { at: '2026-10-01T09:00:00+08:00', event: 'init', detail: 'type=feature' },
    { at: '2026-10-03T09:00:00+08:00', event: 'unit', detail: 'plan-verify 3/5' },
  ],
  created: '2026-10-01T09:00:00+08:00',
  updated: '2026-10-03T09:00:00+08:00',
})

/** T-2：schema v2 feature，phase=verify、verify=PASS、next=/plan-review。 */
export const V2_FEATURE_VERIFY_PASS = text({
  schema_version: 2,
  slug: 'order-export-csv',
  name: '訂單匯出 CSV',
  type: 'feature',
  inferred: false,
  phase: 'verify',
  next: { command: '/plan-review', reason: '驗收 PASS，下一步審查' },
  steps: {
    start: step('done', '2026-10-01T09:00:00+08:00'),
    spec: step('done', '2026-10-01T10:00:00+08:00'),
    db: step('done', '2026-10-01T10:30:00+08:00'),
    arch: step('done', '2026-10-01T11:00:00+08:00'),
    build: step('done', '2026-10-02T15:00:00+08:00'),
    security: step('skipped', '2026-10-02T15:10:00+08:00', '無安全面向變更'),
    verify: step('done', '2026-10-04T09:00:00+08:00'),
    review: step('pending'),
    close: step('pending'),
  },
  work_unit: emptyWorkUnit,
  gates: {
    requirement: { status: 'approved', at: '2026-10-01T10:00:00+08:00', by: 'human', reason: 'ok' },
    architecture: { status: 'approved', at: '2026-10-01T11:00:00+08:00', by: 'human', reason: 'ok' },
    uat: pendingGate,
  },
  resume_hint: { branch: null, services: [], read_first: [] },
  results: {
    verify: { health_score: 96, passed: 6, failed: 0, blocked: 0, skipped: 0, manual: 0, mode: 'full', status: 'PASS' },
    review: {},
    security: {},
  },
  git: { branch: 'feature/order-export-csv', base: 'main', last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  history: [],
  created: '2026-10-01T09:00:00+08:00',
  updated: '2026-10-04T09:00:00+08:00',
})

/** schema v1 feature（沒有 gates），舊流程 close 已 done（normalize 才會把 uat 補成 waived，Cockpit 不得推導）。 */
export const V1_FEATURE_LEGACY = text({
  schema_version: 1,
  slug: 'legacy-report-filter',
  name: '報表篩選條件',
  type: 'feature',
  inferred: false,
  phase: 'build',
  next: { command: '/plan-build', reason: '規劃完成，可以產碼' },
  steps: {
    start: step('done', '2026-08-01T09:00:00+08:00'),
    spec: step('done', '2026-08-01T10:00:00+08:00'),
    db: step('skipped', '2026-08-01T10:00:00+08:00', 'DB_REQUIRED=false'),
    arch: step('done', '2026-08-01T11:00:00+08:00'),
    build: step('in_progress', '2026-08-02T09:00:00+08:00'),
    security: step('pending'),
    verify: step('pending'),
    review: step('pending'),
    close: step('pending'),
  },
  work_unit: emptyWorkUnit,
  resume_hint: { branch: 'feature/legacy-report-filter', services: [], read_first: [] },
  results: { verify: {}, review: {}, security: {} },
  git: { branch: 'feature/legacy-report-filter', base: 'main', last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  created: '2026-08-01T09:00:00+08:00',
  updated: '2026-08-02T09:00:00+08:00',
})

/** schema v2 bug：只有 4 個 steps，gates 三個都在但 bug 只該顯示 uat。 */
export const V2_BUG_MINIMAL = text({
  schema_version: 2,
  slug: 'login-timeout-fix',
  name: '登入逾時判斷錯誤',
  type: 'bug',
  inferred: false,
  phase: 'fix',
  next: { command: '/bug-close', reason: '修復與驗證已完成；進入 /bug-close 做本輪 Human UAT' },
  steps: {
    start: step('done', '2026-09-30T12:00:00+08:00'),
    investigate: step('done', '2026-09-30T12:03:00+08:00'),
    fix: step('done', '2026-09-30T12:28:00+08:00'),
    close: step('pending'),
  },
  work_unit: emptyWorkUnit,
  gates: {
    requirement: pendingGate,
    architecture: pendingGate,
    uat: { status: 'pending', at: '2026-09-30T12:03:45+08:00', by: 'crew', reason: 'fresh human acceptance required' },
  },
  resume_hint: { branch: 'fix/login-timeout', services: [], read_first: [] },
  results: { verify: {}, review: {}, security: {} },
  git: { branch: 'fix/login-timeout', base: null, last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  history: [{ at: '2026-09-30T12:00:00+08:00', event: 'init', detail: 'type=bug' }],
  created: '2026-09-30T12:00:00+08:00',
  updated: '2026-09-30T12:28:00+08:00',
})

/** schema v1 bug：舊版 bug 也帶 9 個 feature steps（照實顯示，不得刪減）。 */
export const V1_BUG_9STEPS = text({
  schema_version: 1,
  slug: 'cache-ttl-bug',
  name: '快取 TTL 未生效',
  type: 'bug',
  inferred: false,
  phase: 'start',
  next: { command: '/plan spec', reason: '規格（目標與驗收條件）尚未產出' },
  steps: {
    start: step('done', '2026-08-27T22:28:41+08:00'),
    spec: step('pending'),
    db: step('pending'),
    arch: step('pending'),
    build: step('pending'),
    security: step('pending'),
    verify: step('pending'),
    review: step('pending'),
    close: step('pending'),
  },
  work_unit: emptyWorkUnit,
  resume_hint: { branch: 'hotfix/cache-ttl-bug', services: [], read_first: [] },
  results: { verify: {}, review: {}, security: {} },
  git: { branch: 'hotfix/cache-ttl-bug', base: 'main', last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  created: '2026-08-27T22:28:41+08:00',
  updated: '2026-08-27T22:28:41+08:00',
})

/** 已結案（close=done）的 v2 feature。 */
export const V2_FEATURE_CLOSED = text({
  schema_version: 2,
  slug: 'profile-avatar-upload',
  name: '大頭貼上傳',
  type: 'feature',
  inferred: false,
  phase: 'close',
  next: { command: null, reason: '任務已結案（close 完成），可用 /plan-start 開新任務' },
  steps: {
    start: step('done', '2026-09-01T09:00:00+08:00'),
    spec: step('done'),
    db: step('skipped'),
    arch: step('done'),
    build: step('done'),
    security: step('pending'),
    verify: step('pending'),
    review: step('done'),
    close: step('done', '2026-10-05T20:00:00+08:00'),
  },
  work_unit: emptyWorkUnit,
  gates: {
    requirement: { status: 'approved', at: null, by: 'human', reason: 'ok' },
    architecture: { status: 'approved', at: null, by: 'human', reason: 'ok' },
    uat: { status: 'approved', at: null, by: 'human', reason: 'ok' },
  },
  resume_hint: { branch: null, services: [], read_first: [] },
  results: { verify: {}, review: { critical: 0, warning: 3, files: 6, mode: 'full', status: 'WARN' }, security: {} },
  git: { branch: 'feature/profile-avatar-upload', base: 'main', last_commit: null },
  notion: { page_id: null, mirrored_status: '已完成', last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  history: [],
  created: '2026-09-01T09:00:00+08:00',
  updated: '2026-10-05T20:00:00+08:00',
})

/** 已擱置（parked 物件）的 v2 feature。 */
export const V2_FEATURE_PARKED = text({
  schema_version: 2,
  slug: 'search-synonyms',
  name: '搜尋同義詞',
  type: 'feature',
  inferred: true,
  phase: 'spec',
  next: { command: '/plan-next search-synonyms', reason: '任務已擱置' },
  steps: {
    start: step('done'),
    spec: step('in_progress'),
    db: step('pending'),
    arch: step('pending'),
    build: step('pending'),
    security: step('pending'),
    verify: step('pending'),
    review: step('pending'),
    close: step('pending'),
  },
  work_unit: emptyWorkUnit,
  gates: { requirement: pendingGate, architecture: pendingGate, uat: pendingGate },
  resume_hint: { branch: null, services: [], read_first: [] },
  results: { verify: {}, review: {}, security: {} },
  git: { branch: null, base: null, last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: { at: '2026-09-20T10:00:00+08:00', reason: '等待需求方回覆' },
  history: [],
  created: '2026-09-10T10:00:00+08:00',
  updated: '2026-10-06T08:00:00+08:00',
})

/** JSON 壞掉（截斷）的 state.json。 */
export const MALFORMED = '{\n  "schema_version": 2,\n  "slug": "broken-task",\n  "steps": {\n    "start": {"status": "done"'

/** 合法 JSON 但不是物件。 */
export const NOT_OBJECT = '["schema_version", 2]'

/** schema 比 Cockpit 測試過的 v2 新。 */
export const V3_FUTURE = text({
  schema_version: 3,
  slug: 'future-schema-task',
  name: '未來格式',
  type: 'feature',
  phase: 'spec',
  steps: { start: step('done'), spec: step('in_progress'), close: step('pending') },
  gates: { requirement: pendingGate, uat: pendingGate },
  created: '2026-10-01T09:00:00+08:00',
  updated: '2026-10-01T09:00:00+08:00',
})

/**
 * T-14 不可信內容：name 含 ANSI escape、換行與 500 字元；next.command 是惡意指令；
 * 目錄名（slug）含空白，由 world 以目錄名提供。
 */
export const HOSTILE_NAME = `\x1b[31m紅字\x1b[0m第一行\n第二行\r\n${'長'.repeat(500)}`

export const HOSTILE = text({
  schema_version: 2,
  slug: 'evil task',
  name: HOSTILE_NAME,
  type: 'feature',
  inferred: false,
  phase: 'spec\x1b[2J',
  next: { command: '/plan-close --force\n/plan-start injected', reason: '\x1b]8;;https://example.invalid\x07點我\x1b]8;;\x07' },
  steps: { start: step('done'), spec: step('in_progress'), close: step('pending') },
  work_unit: emptyWorkUnit,
  gates: { requirement: pendingGate, architecture: pendingGate, uat: pendingGate },
  resume_hint: { branch: 'x\x07y', services: [], read_first: ['a\nb'] },
  results: { verify: { status: 'WARN\x1b[5m', blocked: '2' }, review: {}, security: {} },
  git: { branch: 'feature/\x1b[1mevil', base: null, last_commit: null },
  notion: { page_id: null, mirrored_status: null, last_synced_at: null },
  deploy: { steps_total: 0, steps_confirmed: 0 },
  parked: null,
  created: '2026-10-01T09:00:00+08:00',
  updated: '2026-10-06T09:30:00+08:00',
})

/** references/verification-ir.md Schema v1 形狀：browser×2、api×1、fixture 才有的 custom-x×1。 */
export const VERIFICATION_IR = text({
  schema_version: 1,
  slug: 'push-tag-query',
  scenario: 'push-tag-query-main-flow',
  framework_adapter: 'generic-playwright',
  preconditions: [
    { type: 'authenticated', role: 'admin' },
    { type: 'seed', name: 'tags' },
  ],
  safety: [{ type: 'forbid_request', method: 'POST', url_contains: '/dangerous/update' }],
  acs: {
    'AC-1': {
      verification_type: 'browser',
      steps: [{ action: 'goto', path: '/tags' }],
      assertions: [{ type: 'visible', locator: { strategy: 'role', role: 'table' } }],
    },
    'AC-2': { verification_type: 'api', steps: [{ action: 'api_request', method: 'GET', path: '/api/tags' }], assertions: [] },
    'AC-3': { verification_type: 'browser', steps: [], assertions: [] },
    'AC-4': { verification_type: 'custom-x', steps: [], assertions: [] },
  },
})

/** 壞掉的 IR。 */
export const IR_MALFORMED = '{ "schema_version": 1, "acs": '
