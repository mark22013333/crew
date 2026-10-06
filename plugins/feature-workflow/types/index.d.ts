// CREW Cockpit 的 $.state 契約（Claude Code Mods）。
//
// 本檔是 Cockpit 讀取模型（snapshot）型別的唯一定義處：hooks/cockpit/model.ts
// 只做 re-export 與執行期常數，不得在別處重複宣告這些型別。
// 自成一檔、不 import 任何模組（Mods 契約要求）。
//
// 原則（規格 §31）：state.json 是 truth；Cockpit 只把它讀成「顯示用」的 view model，
// 不 normalize 回寫、不重算 next、不判定 workflow transition。

/** 一個「鍵／值」顯示列；key 與 value 都已經過 §18.1 清理。 */
export type CockpitField = {
  key: string
  value: string
}

/** state.steps 的一列，依檔案中實際存在的 key 與順序，不補齊、不刪減（§11.1）。 */
export type CockpitStepView = {
  /** step key（已清理），例如 start / spec / investigate。 */
  key: string
  /** 原值（已清理）；缺或非字串為 null。合法值見 CS:51，但不在此改判。 */
  status: string | null
  at: string | null
  reason: string | null
}

/** state.gates 的一列（只有 schema v2 才有，v1 整個 gates 為 null）。 */
export type CockpitGateView = {
  /** requirement / architecture / uat ……（已清理，依檔案順序）。 */
  key: string
  /** 原值（已清理）；合法值見 CS:55，不在此改判。 */
  status: string | null
  at: string | null
  by: string | null
  reason: string | null
}

/** state.work_unit 的顯示資料。 */
export type CockpitWorkUnitView = {
  skill: string | null
  /** 以 crew-state.py as_int 語意解析，失敗為 0。 */
  done: number
  /** 以 as_int 語意解析，失敗為 0。 */
  total: number
  label: string
  remaining: string[]
  /** total > 0 且 done < total：工作單元中斷（§11 醒目顯示）。 */
  isInterrupted: boolean
}

/** state.resume_hint（CS:287 形狀 {branch, services, read_first}）。 */
export type CockpitResumeHintView = {
  branch: string | null
  services: string[]
  readFirst: string[]
  /** 三個欄位皆空：不顯示「接續提示」。 */
  isEmpty: boolean
}

/** results.review / results.security 的顯示資料。 */
export type CockpitResultView = {
  /** results.{kind}.status 原值（已清理）；缺為 null。不得改判。 */
  status: string | null
  /** 除 status 以外、檔案中實際存在的摘要 key（依檔案順序，已清理）。 */
  entries: CockpitField[]
  /** 該 results 區塊不存在、不是物件或是空物件。 */
  isEmpty: boolean
}

/**
 * results.verify 的顯示原料（§11.3／§13）。
 * BLOCKED 是「衍生顯示」：status == 'WARN' && blocked > 0；這裡只提供原料，不做映射。
 */
export type CockpitVerifyView = CockpitResultView & {
  /** results.verify.blocked 以 as_int 語意解析（字串 "2" → 2），失敗或缺為 0。 */
  blocked: number
  /** 檔案中是否真的有 blocked 這個 key。 */
  hasBlockedKey: boolean
}

/** 每個 AC 的 route（verification_type 原值）。 */
export type CockpitIrAcView = {
  /** AC id（已清理），例如 AC-1。 */
  id: string
  /** verification_type 原值（已清理）；缺或非字串為 null。 */
  verificationType: string | null
}

/** route 動態統計的一組：依 IR 中實際出現的 verification_type 值分組（§6.4，不得寫死類別）。 */
export type CockpitIrRouteCount = {
  /** verification_type 原值（已清理）；缺或非字串的 AC 歸在 null。 */
  verificationType: string | null
  count: number
}

/**
 * .spec/{slug}/.cache/verification-ir.json 的摘要。
 * - missing：檔案不存在（常態，不是錯誤，§6.4）
 * - ready：可解析的 JSON 物件
 * - invalid：讀取失敗、過大、JSON 壞掉或不是物件（§16 IR invalid）
 */
export type CockpitIrSummary =
  | { status: 'missing' }
  | {
      status: 'invalid'
      /** 已清理的錯誤摘要。 */
      message: string
    }
  | {
      status: 'ready'
      /** IR 的 schema_version 原值；非數字為 null。 */
      schemaVersion: number | null
      acCount: number
      /** 依出現次數由多到少、同數依值排序；null 組排最後。 */
      routes: CockpitIrRouteCount[]
      acs: CockpitIrAcView[]
      preconditionCount: number
      safetyCount: number
    }

/** 一個可解析的 task（.spec/{dir}/state.json 是 JSON 物件）。 */
export type CockpitTaskView = {
  /**
   * 任務識別：.spec 下的目錄名「原值」（與 crew-state.py iter_states 一致，slug 以目錄名為準）。
   * 只能當 key 比對與（通過白名單後）代入 /plan-next；不得直接顯示，顯示請用 slug。
   */
  id: string
  /** 目錄名經 §18.1 清理後的顯示字串。 */
  slug: string
  /** id 符合 ^[a-z0-9][a-z0-9._-]{0,79}$；false 時不得提供 Fill（§14）。 */
  isSlugFillable: boolean
  /** state.json 的絕對路徑（已清理，僅供顯示）。 */
  statePath: string
  /** schema_version 原值；非數字為 null。v1 是常態，不是錯誤。 */
  schemaVersion: number | null
  /** schema_version > 2：需顯示「比 Cockpit 測試過的 v2 新」提示（§16）。 */
  isSchemaNewer: boolean
  /** state.name（已清理）；缺時為 slug。 */
  name: string
  /** state.type 原值（已清理）；缺或非字串為 'feature'（與 normalize 預設一致，但不推導其他欄位）。 */
  type: string
  /** state.phase 原值（已清理）；缺為 null，不得自行推導（normalize 才會推導）。 */
  phase: string | null
  /** state.inferred 依 Python truthiness 判定。 */
  inferred: boolean
  /** parked 為 truthy 時的顯示資料（§8）；否則 null。 */
  parked: { at: string | null; reason: string | null } | null
  /** steps.close.status ∈ {done, skipped}（§8，對齊 CS DONE_LIKE）。 */
  closed: boolean
  /** !closed && !parked。 */
  active: boolean
  /**
   * 對齊 crew-state.py：normalize() 先把 null／缺漏的 updated、created 補成「現在」，
   * 再 stale_days = max(0, floor((now − (parse(updated) or parse(created))) / 1 day))；都解析失敗為 0（CS:299-312、1364-1369）。
   */
  staleDays: number
  /** 補值後 updated 與 created 仍都無法解析（空字串或壞字串；附加資訊，staleDays 仍為 0）。 */
  staleUnknown: boolean
  /**
   * 停滯天數的參考時間（epoch ms）。null 表示 crew-state.py 會算出 0 天：
   * 參考值是被 normalize 補成的「現在」，或兩者都無法解析。增量重讀沿用舊 view 時以它重算 staleDays。
   */
  staleRefMs: number | null
  /** updated 原值（已清理）。 */
  updated: string | null
  /** created 原值（已清理）。 */
  created: string | null
  /** parse(updated) ?? parse(created)，epoch ms；供「最近更新」排序與選取（停滯天數改用 staleRefMs）。 */
  updatedRefMs: number | null
  /** state.next 快照（§6.3）：只能標成「上次記錄的建議」，不得當成現況、不得當成 Fill 內容。 */
  recordedNext: { command: string | null; reason: string } | null
  resumeHint: CockpitResumeHintView | null
  /** 依檔案實際存在的 steps（v2 bug 4 步、v1 bug 可能 9 步），不補齊。 */
  steps: CockpitStepView[]
  /** v1（或 gates 不是物件）為 null：不得顯示 pending（§6.3）。 */
  gates: CockpitGateView[] | null
  workUnit: CockpitWorkUnitView | null
  results: {
    verify: CockpitVerifyView
    review: CockpitResultView
    security: CockpitResultView
  }
  /** state.git 的鍵值（已清理；純文字，不做連結）。 */
  git: CockpitField[]
  /** state.git.branch（已清理）；取自 state，非即時 git 狀態。 */
  branch: string | null
  notion: CockpitField[]
  deploy: CockpitField[]
  verificationIr: CockpitIrSummary
}

/** 無法解析成 task 的 state.json（Cockpit 刻意列出；/plan-status 不會列出此筆，§6.2）。 */
export type CockpitInvalidTask = {
  /** 目錄名原值（僅作 key）。 */
  id: string
  /** 目錄名清理後的顯示字串。 */
  slug: string
  statePath: string
  /** parse：JSON 壞掉；not-object：不是 JSON 物件；too-large：超過 4 MiB；read：其他讀取失敗。 */
  kind: 'parse' | 'not-object' | 'too-large' | 'read'
  /** 已清理的錯誤摘要。 */
  message: string
}

/** 非單一 task 的載入問題（例如 .spec 無法列出）。 */
export type CockpitError = {
  scope: 'spec-dir' | 'loader'
  path: string | null
  message: string
}

/** 自動選取的理由（§8）。 */
export type CockpitSelectionReason = 'user' | 'only-active' | 'latest-active' | 'none'

/** 存在 $.state 的讀取模型（§7）。render 只讀它，不做 I/O（§3 D-3）。 */
export type CockpitSnapshot = {
  /** 讀取模型版本；熱重載後版本不同時 loader 會丟棄舊快取。 */
  modelVersion: number
  /** 含 .spec/ 的 repo root（§6.1）；沒有則 null（＝無 CREW 任務）。 */
  repoRoot: string | null
  /** repoRoot 取自哪個候選。 */
  rootSource: 'session-root' | 'ancestor' | 'git-root' | null
  /** 載入完成時間（epoch ms，取自 $.clock.now）。 */
  loadedAt: number
  /** 可解析的 task，已排序：active → parked → closed，各組內 updated 新到舊、再依 id。 */
  tasks: CockpitTaskView[]
  /** 無法解析的 state.json。 */
  invalidTasks: CockpitInvalidTask[]
  /** .spec 下沒有 state.json 的目錄數（§6.2）。 */
  untrackedDirCount: number
  /** active task 數。 */
  activeCount: number
  /** 載入當下的選取結果（task id）；render 端請用 selectors.resolveSelection 搭配 selectedSlug atom 即時計算。 */
  selectedSlug: string | null
  /** selectionReason === 'latest-active'（多個 active 時自動選最新，§8-3）。 */
  autoSelected: boolean
  selectionReason: CockpitSelectionReason
  errors: CockpitError[]
  /** path → mtimeMs（state.json 與 IR），供 §15 增量重讀。 */
  mtimes: Record<string, number>
  /** path → size，與 mtimes 一起當指紋。 */
  sizes: Record<string, number>
  /** 本次載入的讀檔統計（診斷／測試用）。 */
  stats: { dirs: number; reread: number; reused: number }
}

/** Claude Code 版本檢查結果（§19）。 */
export type CockpitRuntime = {
  isSupported: boolean
  version: string | null
  minimum: string
  /**
   * 最近一次 refresh 領到的世代號（遞增）。存在 $.state 而非模組變數：熱重載後舊模組還在跑的 refresh
   * 也看得到新世代，不會把較舊的結果寫回 snapshot。缺值視為 0。
   */
  refreshGeneration?: number
  /**
   * 任務 tab 的「已結案」分組是否展開（UI state，按 e 切換）。缺值視為收合（只顯示最近 5 筆）。
   * 放在 runtime 而非新 key：不增加 Mod 的 state 讀寫清單（capability baseline 不變）。
   */
  isClosedExpanded?: boolean
}

/** Cockpit pane 的 tab（UI state，§10）。 */
export type CockpitTab = 'overview' | 'tasks' | 'verify'

declare module 'claude-code' {
  interface PluginState {
    'feature-workflow': {
      /** 最新讀取模型；尚未載入為 null。 */
      snapshot: CockpitSnapshot | null
      /** 使用者在本 session 選的 task id（UI state，不是 workflow state）。 */
      selectedSlug: string | null
      /** pane 目前的 tab。 */
      tab: CockpitTab
      /** HUD 開關鏡像（§9.4；真正保存在 $.store）。 */
      hudEnabled: boolean
      /** 版本檢查結果（§19）。 */
      runtime: CockpitRuntime | null
    }
  }
}
