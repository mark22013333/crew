// CREW Cockpit loader：repo-local、唯讀。
//
// 只透過 LoaderPorts 使用 $.session.root/repo、$.fs.list/stat/exists/read 與 $.clock.now；
// 不寫檔、不跑 process、不呼叫 model、不連網（規格 §0、§3 D-2）。
// 不在 TypeScript 重寫 normalize()/compute_next()（§6.3）：只把 state.json 原貌讀成顯示用 view model。

import type { FsEntry, FsStat, SessionRepo } from 'claude-code'

import {
  type CockpitError,
  type CockpitField,
  type CockpitGateView,
  type CockpitInvalidTask,
  type CockpitIrAcView,
  type CockpitIrRouteCount,
  type CockpitIrSummary,
  type CockpitResultView,
  type CockpitResumeHintView,
  type CockpitSelectionReason,
  type CockpitSnapshot,
  type CockpitStepView,
  type CockpitTaskView,
  type CockpitVerifyView,
  type CockpitWorkUnitView,
  DONE_LIKE,
  MAX_FILE_BYTES,
  MAX_KNOWN_SCHEMA,
  MODEL_VERSION,
  TEXT,
  asInt,
  isFillableSlug,
  isTruthy,
  parseIsoMs,
  sanitizeOrNull,
  sanitizeText,
  staleDaysOf,
} from './model'

/**
 * loader 需要的唯讀 I/O 埠。由 crew-cockpit.ts 以 `$.fs.*`／`$.session.*`／`$.clock.now` 綁定
 * （Mods 規定 $ 不能跨 import 傳遞，見 claude plugin validate）；測試可用記憶體實作替代。
 * 這裡刻意沒有 write：loader 不寫任何檔案。
 */
export type LoaderPorts = {
  list: (path: string) => Promise<readonly FsEntry[]>
  stat: (path: string) => Promise<FsStat>
  exists: (path: string) => Promise<boolean>
  read: (path: string) => Promise<string>
  sessionRoot: () => Promise<string>
  repo: () => Promise<SessionRepo | null>
  now: () => Promise<number>
}

/** loadCockpitSnapshot 的選項。 */
export type LoadOptions = {
  /** 上一份 snapshot；用來做 §15 增量重讀。null 表示全量載入。 */
  previous: CockpitSnapshot | null
  /** 使用者本 session 選的 task id（§8 優先序 1）。 */
  userSelectedSlug: string | null
}

/** repo root 判定結果（§6.1）。 */
export type RepoRootResult = {
  root: string | null
  source: CockpitSnapshot['rootSource']
}

type Json = Record<string, unknown>

const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const errorText = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  return typeof error === 'string' ? error : String(error)
}

const isTooLargeError = (error: unknown): boolean => /4\s*MiB|too large|over\s+4|EFBIG/i.test(errorText(error))

// ---------------------------------------------------------------------------
// 路徑工具（不依賴 Node path）
// ---------------------------------------------------------------------------

const sepOf = (path: string): string => (path.includes('/') || !path.includes('\\') ? '/' : '\\')

/** 以 path 自身的分隔符號接上子路徑。 */
export function joinPath(base: string, ...parts: string[]): string {
  const sep = sepOf(base)
  const trimmed = base.length > 1 ? base.replace(/[\\/]+$/, '') : base
  return [trimmed === sep ? '' : trimmed, ...parts].join(sep)
}

const parentOf = (path: string): string | null => {
  const sep = sepOf(path)
  const trimmed = path.replace(/[\\/]+$/, '')
  const cut = trimmed.lastIndexOf(sep)
  if (cut < 0) {
    return null
  }
  if (cut === 0) {
    return trimmed === sep ? null : sep
  }
  const parent = trimmed.slice(0, cut)
  // Windows 磁碟根（C:）保留分隔符號
  return /^[A-Za-z]:$/.test(parent) ? parent + sep : parent
}

const samePath = (a: string, b: string): boolean => a.replace(/[\\/]+$/, '') === b.replace(/[\\/]+$/, '')

const isUnder = (child: string, ancestor: string): boolean => {
  const a = ancestor.replace(/[\\/]+$/, '')
  const c = child.replace(/[\\/]+$/, '')
  return c === a || c.startsWith(a + sepOf(ancestor))
}

const hasSpecDir = async (io: LoaderPorts, dir: string): Promise<boolean> => {
  try {
    const path = joinPath(dir, '.spec')
    // exists 不會 reject：先問，避免缺檔的 stat 進錯誤 log
    if (!(await io.exists(path))) {
      return false
    }
    const stat = await io.stat(path)
    return stat.kind === 'dir'
  } catch {
    return false
  }
}

/**
 * §6.1 repo root：依序檢查，第一個含 .spec/ 目錄者勝出。
 * 1. $.session.root()（啟動目錄／worktree 位置，不是 git 根）
 * 2. 從 session root 逐層往上，最多到 git 根（session root 必須在 git 根之下才走）
 * 3. $.session.repo()?.root（worktree 時是主工作樹，只能當最後 fallback）
 * 都沒有 → null（例如多 repo workspace 根目錄；不往下掃 sub-repo）。
 */
export async function resolveRepoRoot(io: LoaderPorts): Promise<RepoRootResult> {
  let sessionRoot: string | null = null
  try {
    sessionRoot = await io.sessionRoot()
  } catch {
    sessionRoot = null
  }
  let gitRoot: string | null = null
  try {
    gitRoot = (await io.repo())?.root ?? null
  } catch {
    gitRoot = null
  }

  if (sessionRoot !== null && sessionRoot !== '') {
    if (await hasSpecDir(io, sessionRoot)) {
      return { root: sessionRoot, source: 'session-root' }
    }
    if (gitRoot !== null && !samePath(sessionRoot, gitRoot) && isUnder(sessionRoot, gitRoot)) {
      let current = parentOf(sessionRoot)
      // 往上走到（含）git 根為止
      while (current !== null && isUnder(current, gitRoot)) {
        if (await hasSpecDir(io, current)) {
          return { root: current, source: 'ancestor' }
        }
        if (samePath(current, gitRoot)) {
          return { root: null, source: null }
        }
        current = parentOf(current)
      }
    }
  }
  if (gitRoot !== null && gitRoot !== '' && (sessionRoot === null || !samePath(sessionRoot, gitRoot))) {
    if (await hasSpecDir(io, gitRoot)) {
      return { root: gitRoot, source: 'git-root' }
    }
  }
  return { root: null, source: null }
}

// ---------------------------------------------------------------------------
// tolerant parser：state.json 原貌 → CockpitTaskView
// ---------------------------------------------------------------------------

const fieldsOf = (value: unknown, skip: readonly string[] = []): CockpitField[] => {
  if (!isObject(value)) {
    return []
  }
  return Object.entries(value)
    .filter(([key]) => !skip.includes(key))
    .map(([key, raw]) => ({ key: sanitizeText(key), value: sanitizeText(raw) }))
}

const stringList = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(item => sanitizeText(item)).filter(item => item !== '') : []

const stepsOf = (value: unknown): CockpitStepView[] => {
  if (!isObject(value)) {
    return []
  }
  return Object.entries(value).map(([key, raw]) => {
    const entry = isObject(raw) ? raw : {}
    return {
      key: sanitizeText(key),
      status: typeof entry.status === 'string' ? sanitizeOrNull(entry.status) : null,
      at: sanitizeOrNull(entry.at),
      reason: sanitizeOrNull(entry.reason),
    }
  })
}

const gatesOf = (value: unknown): CockpitGateView[] | null => {
  if (!isObject(value)) {
    return null
  }
  return Object.entries(value).map(([key, raw]) => {
    const entry = isObject(raw) ? raw : {}
    return {
      key: sanitizeText(key),
      status: typeof entry.status === 'string' ? sanitizeOrNull(entry.status) : null,
      at: sanitizeOrNull(entry.at),
      by: sanitizeOrNull(entry.by),
      reason: sanitizeOrNull(entry.reason),
    }
  })
}

const workUnitOf = (value: unknown): CockpitWorkUnitView | null => {
  if (!isObject(value)) {
    return null
  }
  const done = asInt(value.done)
  const total = asInt(value.total)
  return {
    skill: sanitizeOrNull(value.skill),
    done,
    total,
    label: sanitizeText(value.label),
    remaining: stringList(value.remaining),
    isInterrupted: total > 0 && done < total,
  }
}

const resumeHintOf = (value: unknown): CockpitResumeHintView | null => {
  if (!isObject(value)) {
    return null
  }
  const branch = sanitizeOrNull(value.branch)
  const services = stringList(value.services)
  const readFirst = stringList(value.read_first)
  return { branch, services, readFirst, isEmpty: branch === null && services.length === 0 && readFirst.length === 0 }
}

const resultOf = (value: unknown): CockpitResultView => {
  if (!isObject(value)) {
    return { status: null, entries: [], isEmpty: true }
  }
  return {
    status: sanitizeOrNull(value.status),
    entries: fieldsOf(value, ['status']),
    isEmpty: Object.keys(value).length === 0,
  }
}

const verifyOf = (value: unknown): CockpitVerifyView => {
  const base = resultOf(value)
  const hasBlockedKey = isObject(value) && Object.prototype.hasOwnProperty.call(value, 'blocked')
  return { ...base, blocked: hasBlockedKey ? asInt((value as Json).blocked) : 0, hasBlockedKey }
}

const nextOf = (value: unknown): CockpitTaskView['recordedNext'] => {
  if (!isObject(value)) {
    return null
  }
  return { command: sanitizeOrNull(value.command), reason: sanitizeText(value.reason) }
}

const parkedOf = (value: unknown): CockpitTaskView['parked'] => {
  if (!isTruthy(value)) {
    return null
  }
  if (isObject(value)) {
    return { at: sanitizeOrNull(value.at), reason: sanitizeOrNull(value.reason) }
  }
  return { at: null, reason: sanitizeOrNull(value) }
}

const schemaOf = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

/**
 * state.json（已確定是 JSON 物件）→ task view。純函式，不做 I/O。
 * @param raw state.json 的物件
 * @param id .spec 下的目錄名原值（crew-state.py 以目錄名為 slug）
 * @param statePath state.json 的路徑
 * @param ir 已讀好的 IR 摘要
 * @param nowMs 用於停滯天數
 */
export function toTaskView(
  raw: Json,
  id: string,
  statePath: string,
  ir: CockpitIrSummary,
  nowMs: number,
): CockpitTaskView {
  const slug = sanitizeText(id)
  const schemaVersion = schemaOf(raw.schema_version)
  const steps = isObject(raw.steps) ? raw.steps : {}
  const close = isObject(steps.close) ? steps.close : {}
  const closed = typeof close.status === 'string' && DONE_LIKE.includes(close.status)
  const parked = parkedOf(raw.parked)
  const updatedMs = parseIsoMs(raw.updated)
  const updatedRefMs = updatedMs ?? parseIsoMs(raw.created)
  const git = fieldsOf(raw.git)
  const name = sanitizeText(raw.name)
  const type = typeof raw.type === 'string' && raw.type !== '' ? sanitizeText(raw.type) : 'feature'
  const results = isObject(raw.results) ? raw.results : {}

  return {
    id,
    slug,
    isSlugFillable: isFillableSlug(id),
    statePath: sanitizeText(statePath),
    schemaVersion,
    isSchemaNewer: schemaVersion !== null && schemaVersion > MAX_KNOWN_SCHEMA,
    name: name === '' ? slug : name,
    type: type === '' ? 'feature' : type,
    phase: sanitizeOrNull(raw.phase),
    inferred: isTruthy(raw.inferred),
    parked,
    closed,
    active: !closed && parked === null,
    staleDays: staleDaysOf(updatedRefMs, nowMs),
    staleUnknown: updatedRefMs === null,
    updated: sanitizeOrNull(raw.updated),
    created: sanitizeOrNull(raw.created),
    updatedRefMs,
    recordedNext: nextOf(raw.next),
    resumeHint: resumeHintOf(raw.resume_hint),
    steps: stepsOf(raw.steps),
    gates: gatesOf(raw.gates),
    workUnit: workUnitOf(raw.work_unit),
    results: {
      verify: verifyOf(results.verify),
      review: resultOf(results.review),
      security: resultOf(results.security),
    },
    git,
    branch: isObject(raw.git) ? sanitizeOrNull(raw.git.branch) : null,
    notion: fieldsOf(raw.notion),
    deploy: fieldsOf(raw.deploy),
    verificationIr: ir,
  }
}

/**
 * Verification IR（已確定是可解析的 JSON）→ 摘要。純函式。
 * route 依 verification_type 的實際值動態分組（§6.4），不寫死類別。
 */
export function toIrSummary(raw: unknown): CockpitIrSummary {
  if (!isObject(raw)) {
    return { status: 'invalid', message: 'verification-ir.json 不是 JSON 物件' }
  }
  const acEntries: [string, unknown][] = isObject(raw.acs)
    ? Object.entries(raw.acs)
    : Array.isArray(raw.acs)
      ? raw.acs.map((item, index) => [isObject(item) && typeof item.id === 'string' ? item.id : `#${index + 1}`, item])
      : []
  const acs: CockpitIrAcView[] = acEntries.map(([key, value]) => ({
    id: sanitizeText(key),
    verificationType:
      isObject(value) && typeof value.verification_type === 'string'
        ? sanitizeOrNull(value.verification_type)
        : null,
  }))
  const counts = new Map<string | null, number>()
  for (const ac of acs) {
    counts.set(ac.verificationType, (counts.get(ac.verificationType) ?? 0) + 1)
  }
  const routes: CockpitIrRouteCount[] = [...counts.entries()]
    .map(([verificationType, count]) => ({ verificationType, count }))
    .sort((a, b) => {
      if (a.verificationType === null || b.verificationType === null) {
        return a.verificationType === null ? (b.verificationType === null ? 0 : 1) : -1
      }
      return b.count - a.count || (a.verificationType < b.verificationType ? -1 : a.verificationType > b.verificationType ? 1 : 0)
    })
  return {
    status: 'ready',
    schemaVersion: schemaOf(raw.schema_version),
    acCount: acs.length,
    routes,
    acs,
    preconditionCount: Array.isArray(raw.preconditions) ? raw.preconditions.length : 0,
    safetyCount: Array.isArray(raw.safety) ? raw.safety.length : 0,
  }
}

// ---------------------------------------------------------------------------
// 選取（§8）與排序（§12）
// ---------------------------------------------------------------------------

const byUpdatedDesc = (a: CockpitTaskView, b: CockpitTaskView): number => {
  const ma = a.updatedRefMs ?? Number.NEGATIVE_INFINITY
  const mb = b.updatedRefMs ?? Number.NEGATIVE_INFINITY
  if (ma !== mb) {
    return mb > ma ? 1 : -1
  }
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

const groupOf = (task: CockpitTaskView): number => (task.closed ? 2 : task.parked !== null ? 1 : 0)

/** §12 排序：active → parked → closed，各組內 updated 新到舊，同時間依 id。 */
export function sortTasks(tasks: readonly CockpitTaskView[]): CockpitTaskView[] {
  return [...tasks].sort((a, b) => groupOf(a) - groupOf(b) || byUpdatedDesc(a, b))
}

/**
 * §8 選取優先序：
 * 1. 使用者本 session 已選、且 task 仍存在 → user
 * 2. 只有一個 active → only-active
 * 3. 多個 active → updated 最新者 → latest-active（autoSelected）
 * 4. 沒有 active → none
 */
export function selectTask(
  tasks: readonly CockpitTaskView[],
  userSelectedSlug: string | null,
): { slug: string | null; reason: CockpitSelectionReason } {
  if (userSelectedSlug !== null && tasks.some(task => task.id === userSelectedSlug)) {
    return { slug: userSelectedSlug, reason: 'user' }
  }
  const active = tasks.filter(task => task.active)
  if (active.length === 1) {
    return { slug: active[0]?.id ?? null, reason: 'only-active' }
  }
  if (active.length > 1) {
    return { slug: [...active].sort(byUpdatedDesc)[0]?.id ?? null, reason: 'latest-active' }
  }
  return { slug: null, reason: 'none' }
}

// ---------------------------------------------------------------------------
// I/O：讀檔與增量重讀（§6.2、§15）
// ---------------------------------------------------------------------------

type FileProbe = { kind: 'missing' } | { kind: 'other' } | { kind: 'file'; mtimeMs: number; size: number }

const probe = async (io: LoaderPorts, path: string): Promise<FileProbe> => {
  try {
    if (!(await io.exists(path))) {
      return { kind: 'missing' }
    }
    const stat = await io.stat(path)
    if (stat.kind !== 'file') {
      return { kind: 'other' }
    }
    return { kind: 'file', mtimeMs: stat.mtimeMs, size: stat.size }
  } catch {
    // ENOENT 與權限錯誤一律視為「沒有這個檔」（與 Path.is_file() 回 False 一致）
    return { kind: 'missing' }
  }
}

type ReadJson = { ok: true; value: unknown } | { ok: false; kind: CockpitInvalidTask['kind']; message: string }

const readJson = async (io: LoaderPorts, path: string, size: number): Promise<ReadJson> => {
  if (size > MAX_FILE_BYTES) {
    return { ok: false, kind: 'too-large', message: TEXT.fileTooLarge }
  }
  let text: string
  try {
    text = await io.read(path)
  } catch (error) {
    return isTooLargeError(error)
      ? { ok: false, kind: 'too-large', message: TEXT.fileTooLarge }
      : { ok: false, kind: 'read', message: sanitizeText(`讀取失敗：${errorText(error)}`) }
  }
  try {
    return { ok: true, value: JSON.parse(text) as unknown }
  } catch (error) {
    return { ok: false, kind: 'parse', message: sanitizeText(`${TEXT.invalidState}：${errorText(error)}`) }
  }
}

const loadIr = async (
  io: LoaderPorts,
  path: string,
  previous: CockpitSnapshot | null,
  previousIr: CockpitIrSummary | undefined,
  mtimes: Record<string, number>,
  sizes: Record<string, number>,
): Promise<{ ir: CockpitIrSummary; reread: boolean }> => {
  const found = await probe(io, path)
  if (found.kind !== 'file') {
    return { ir: { status: 'missing' }, reread: false }
  }
  mtimes[path] = found.mtimeMs
  sizes[path] = found.size
  if (
    previous !== null &&
    previousIr !== undefined &&
    previousIr.status !== 'missing' &&
    previous.mtimes[path] === found.mtimeMs &&
    previous.sizes[path] === found.size
  ) {
    return { ir: previousIr, reread: false }
  }
  const read = await readJson(io, path, found.size)
  if (!read.ok) {
    return { ir: { status: 'invalid', message: read.message }, reread: true }
  }
  return { ir: toIrSummary(read.value), reread: true }
}

/** 列出 .spec 第一層的「目錄」名稱（一般檔案如 _index.md 略過；指向目錄的連結算目錄）。 */
const listSpecDirs = async (io: LoaderPorts, specDir: string): Promise<string[]> => {
  const entries = await io.list(specDir)
  const names: string[] = []
  for (const entry of entries) {
    if (entry.kind === 'dir') {
      names.push(entry.name)
    } else if (entry.kind === 'other' && entry.isLink) {
      try {
        const stat = await io.stat(joinPath(specDir, entry.name))
        if (stat.kind === 'dir') {
          names.push(entry.name)
        }
      } catch {
        // 斷掉的連結：略過（與 Path.is_dir() 一致）
      }
    }
  }
  return names.sort()
}

/**
 * 載入 Cockpit snapshot（§6、§7、§8、§15）。唯讀；任何單檔錯誤都不 throw。
 * - 只掃 .spec 第一層目錄；缺 state.json 的目錄只計數。
 * - state.json 壞掉／過大／不是物件 → invalidTasks（/plan-status 不會列出，Cockpit 刻意列出）。
 * - 增量：state.json 與 IR 的 mtime+size 與上一份相同就沿用舊 view（停滯天數仍以 now 重算）。
 */
export async function loadCockpitSnapshot(io: LoaderPorts, options: LoadOptions): Promise<CockpitSnapshot> {
  const nowMs = await io.now()
  const errors: CockpitError[] = []
  const { root, source } = await resolveRepoRoot(io)

  const empty = (extra: Partial<CockpitSnapshot> = {}): CockpitSnapshot => ({
    modelVersion: MODEL_VERSION,
    repoRoot: root,
    rootSource: source,
    loadedAt: nowMs,
    tasks: [],
    invalidTasks: [],
    untrackedDirCount: 0,
    activeCount: 0,
    selectedSlug: null,
    autoSelected: false,
    selectionReason: 'none',
    errors,
    mtimes: {},
    sizes: {},
    stats: { dirs: 0, reread: 0, reused: 0 },
    ...extra,
  })

  if (root === null) {
    return empty()
  }

  const previous =
    options.previous !== null &&
    options.previous.modelVersion === MODEL_VERSION &&
    options.previous.repoRoot === root
      ? options.previous
      : null
  const previousTasks = new Map((previous?.tasks ?? []).map(task => [task.id, task]))

  const specDir = joinPath(root, '.spec')
  let dirs: string[]
  try {
    dirs = await listSpecDirs(io, specDir)
  } catch (error) {
    errors.push({ scope: 'spec-dir', path: sanitizeText(specDir), message: sanitizeText(errorText(error)) })
    return empty()
  }

  const mtimes: Record<string, number> = {}
  const sizes: Record<string, number> = {}
  const tasks: CockpitTaskView[] = []
  const invalidTasks: CockpitInvalidTask[] = []
  let untracked = 0
  let reread = 0
  let reused = 0

  for (const id of dirs) {
    const statePath = joinPath(specDir, id, 'state.json')
    const irPath = joinPath(specDir, id, '.cache', 'verification-ir.json')
    try {
      const found = await probe(io, statePath)
      if (found.kind !== 'file') {
        untracked += 1
        continue
      }
      mtimes[statePath] = found.mtimeMs
      sizes[statePath] = found.size
      const before = previousTasks.get(id)
      const { ir, reread: irReread } = await loadIr(io, irPath, previous, before?.verificationIr, mtimes, sizes)
      if (irReread) {
        reread += 1
      }
      const isSame =
        before !== undefined &&
        previous !== null &&
        previous.mtimes[statePath] === found.mtimeMs &&
        previous.sizes[statePath] === found.size
      if (isSame && before !== undefined) {
        reused += 1
        tasks.push({ ...before, staleDays: staleDaysOf(before.updatedRefMs, nowMs), verificationIr: ir })
        continue
      }
      reread += 1
      const read = await readJson(io, statePath, found.size)
      if (!read.ok) {
        invalidTasks.push({ id, slug: sanitizeText(id), statePath: sanitizeText(statePath), kind: read.kind, message: read.message })
        continue
      }
      if (!isObject(read.value)) {
        invalidTasks.push({ id, slug: sanitizeText(id), statePath: sanitizeText(statePath), kind: 'not-object', message: TEXT.notObject })
        continue
      }
      tasks.push(toTaskView(read.value, id, statePath, ir, nowMs))
    } catch (error) {
      // 任何未預期錯誤只影響這一筆
      invalidTasks.push({
        id,
        slug: sanitizeText(id),
        statePath: sanitizeText(statePath),
        kind: 'read',
        message: sanitizeText(errorText(error)),
      })
    }
  }

  const sorted = sortTasks(tasks)
  const selection = selectTask(sorted, options.userSelectedSlug)
  return empty({
    tasks: sorted,
    invalidTasks,
    untrackedDirCount: untracked,
    activeCount: sorted.filter(task => task.active).length,
    selectedSlug: selection.slug,
    autoSelected: selection.reason === 'latest-active',
    selectionReason: selection.reason,
    mtimes,
    sizes,
    stats: { dirs: dirs.length, reread, reused },
  })
}
