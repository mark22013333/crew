# 開發與發版指南

## 新增／刪除 Skill Checklist

動到 `plugins/{plugin}/skills/` 的目錄時，**同一個 commit** 必須同步：

- `plugins/{plugin}/.claude-plugin/plugin.json` 的 `"skills"` 陣列 —— 新增要加、刪除要移除
- `plugins/{plugin}/README.md` 與根 `README.md` 的指令表
- `CHANGELOG.md`

> **易錯點**：`lint-skills.py`、`lint-readme-sync.py` 都以「掃 `skills/` 實際目錄」為基準，
> 抓不到陣列與目錄不一致。feature-workflow@5.0.0 刪了三個 skill 目錄卻沒改陣列，
> 導致 Claude Code 載入時報 `skills path not found`，存活 37 天才被發現。
> 現由 `scripts/lint-plugin-manifest.py` 把關（CI job `plugin-manifest`）。

## 版本升級 Checklist

升版時**必須完成以下所有步驟**，缺一不可：

### 1. 修改版號（四個地方）

- `plugins/{plugin}/.claude-plugin/plugin.json` 的 `"version"` 欄位 — **這是 `claude plugin update` 判斷是否有新版的依據**
- `plugins/{plugin}/plugin.json` 的 `"version"` 欄位 — Agent Plugins portable canonical manifest
- `.claude-plugin/marketplace.json` 對應 plugin 的 `"version"` 欄位
- `plugins/{plugin}/README.md` 第一行的 `` `vX.Y.Z` `` 標記

> **易錯點**：只改 README 不改 plugin.json，會導致 update 認為「已是最新」不會重新安裝。

### 2. 更新 CHANGELOG.md

在根目錄 `CHANGELOG.md` 新增版本區塊，格式：

```markdown
## [{plugin}@{version}] - {YYYY-MM-DD}

### 新增
- **功能名稱** — 一句話說明

### 改善
- **改善項目** — 一句話說明
```

- `/crew-upgrade` 讀取此檔案顯示更新摘要，**沒寫就等於沒更新**
- 條目從 git diff 和 commit message 提取，確保完整

### 3. 同步 README

需同步更新的 README 共三份：

| 檔案 | 需更新的內容 |
|------|-------------|
| `plugins/{plugin}/README.md` | 版號、功能說明、指令表、前置條件 |
| `README.md`（根目錄） | 指令表、流程圖、前置條件 |

**常見遺漏**：根目錄 README 的指令說明欄（如 plan-verify 的功能描述）未同步。

### 4. Commit

```bash
# 功能 commit（先提交）
git commit -m "feat({scope}): {功能說明}"

# 升版 commit（最後提交）
git commit -m "chore({plugin}): 升版至 v{X.Y.Z}"
```

升版 commit 應包含：版號修改 + CHANGELOG 更新 + README 同步。

### 5. 發佈（push + tag + GitHub Release）

**驗證通過就要發佈**——同事是靠 `claude plugin update` 抓 repo 的 `plugin.json`，
沒 push 就等於沒發版；沒 tag／Release 就無法回頭指認「某版到底是哪個 commit」。

```bash
# 5-1 本地先跑完等效 CI（見下方「本地 CI」），全綠才 push
git push origin {正式分支}

# 5-2 確認 GitHub Actions 全綠
gh run list --limit 1

# 5-3 打 annotated tag（命名：{plugin}-v{X.Y.Z}），指向已驗證的 release commit
git tag -a {plugin}-v{X.Y.Z} -m "{plugin} v{X.Y.Z} — {一句話}" {commit}
git push origin {plugin}-v{X.Y.Z}

# 5-4 建 GitHub Release，release notes 用 CHANGELOG 的該版區塊
gh release create {plugin}-v{X.Y.Z} --title "{plugin} v{X.Y.Z} — {一句話}" --notes-file {notes}
```

- 兩個 plugin **各自一個 tag／Release**（版號獨立遞增），即使同一批 commit 也要各打一個。
- 發佈後用**獨立於建立工具的命令**回驗，不要只信剛才的指令輸出：
  `git ls-remote --tags origin`（遠端真的有 tag）、`git rev-list -n1 {tag}`（指向正確 commit）、
  `gh release view {tag}`（`draft=false`）。
- 同事更新方式：`claude plugin update {plugin}@company-marketplace`，更新後**重啟 Claude Code**。

### 本地 CI（push 前必跑，用 CI 指定的 Python 版本）

`.github/workflows/lint.yml` 用 `python-version: '3.11'`，本機請用對應版本（例 `/opt/homebrew/bin/python3.11`）：

```bash
bash scripts/bump-version.sh --check      # 版本一致性（Claude + portable plugin.json / marketplace / README 四處）
python3.11 scripts/lint-plugin-manifest.py # Claude/portable manifest、hooks、Claude/Codex marketplace 與實際檔案相符
python3.11 scripts/lint-skills.py         # SKILL.md frontmatter 與行數
python3.11 scripts/check-shared-refs.py   # 共用 reference sha256 防漂移
python3.11 scripts/lint-changelog.py      # CHANGELOG 版本／日期排序
python3.11 scripts/lint-agent-model.py --strict   # 模型分工政策（違規阻擋）\npython3.11 scripts/lint-host-portability.py --strict # Host-specific orchestration 防回歸
python3.11 scripts/lint-skill-contract.py # 觸發詞與內部連結
python3.11 scripts/lint-readme-sync.py    # README 指令表同步
python3.11 scripts/lint-state-writers.py --strict  # 狀態單一寫者防回歸（違規阻擋）
# .spec 漂移偵測（script 尚未建立時 CI 會跳過，本地同理）
python3.11 plugins/feature-workflow/scripts/check-spec-drift.py --all --strict
```

> **易錯點**：本地 lint 讀工作區、CI 讀 commit。commit 後 push 前先跑 `git status`
> 確認沒有漏 `git add` 的版本檔（版本檔散在 repo 根與子目錄），必要時用
> `git show HEAD:{檔案}` 抽驗 commit 內容。

---

## 版號規則

- **Major（X）**：破壞性變更（設定格式不相容、Skill 行為大改）
- **Minor（Y）**：新功能、新 Skill
- **Patch（Z）**：Bug 修復、文案修正、小改善

兩個 Plugin 版號獨立遞增。**當前版號不寫在本檔**（會過期），一律查權威來源：

```bash
bash scripts/bump-version.sh --check   # 印出兩個 plugin 的當前版號
```

---

## 檔案結構

```
company-marketplace/
├── .agents/plugins/      # Codex repo marketplace
├── .claude-plugin/       # Claude Code marketplace
├── .github/workflows/    # CI lint（版本一致性、manifest 宣告一致性、SKILL.md 格式、共用 ref 漂移）
├── .gitignore
├── CHANGELOG.md          # 所有 Plugin 的變更紀錄（/crew-upgrade 讀取）
├── CONTRIBUTING.md       # 本文件
├── README.md             # 根目錄總覽（安裝、流程、指令表）
├── scripts/              # 版本同步、lint
└── plugins/
    ├── bug-workflow/
    │   ├── plugin.json   # Portable Agent Plugins manifest
    │   ├── README.md     # Bug Workflow 詳細文件
    │   ├── references/   # 共用 reference（與 feature-workflow 同步，CI 防漂移）
    │   └── skills/       # 各 Skill 的 SKILL.md
    └── feature-workflow/
        ├── plugin.json   # Portable Agent Plugins manifest
        ├── README.md     # Feature Workflow 詳細文件
        ├── references/   # 共用 reference + 專屬 reference
        └── skills/       # 各 Skill 的 SKILL.md
```

---

## `.spec/` 目錄規範

`.spec/{slug}/` 是 `/plan-start` 建立的本地任務目錄，**預設不入版控**
（已寫入 `.gitignore` 的 `.spec/*/`）。

### 何時應該 commit `.spec/`？

只有「對外設計文件」性質的內容才入版控：

- ✅ 套件本身的改進計畫（如 `.spec/crew-improvement/`）
- ✅ 重大架構決策的設計文件（之後可能改為 `docs/adr/`）
- ❌ 個人 dogfood 的暫存 spec
- ❌ 在客戶專案內 `/plan-start` 產生的工作目錄

### 如何 commit「對外設計」目錄

由於 `.gitignore` 預設排除 `.spec/*/`，需強制加入：

```bash
git add -f .spec/{slug}/
```

並建議在 `.gitignore` 的「白名單」段落明示意圖：

```gitignore
!.spec/{slug}/
```

---

## 共用 reference 同步規則

`plugins/bug-workflow/references/` 與 `plugins/feature-workflow/references/`
各自帶以下檔案的副本（為了 plugin 可獨立安裝）：

- `prerequisites.md`
- `db-templates.md`
- `discipline-preamble.md`
- `notion-backend.md`
- `handoff-discipline.md`
- `model-policy.md`
- `host-capabilities.md`
- `model-routing.json`

**單一權威來源（C9）**：`plugins/bug-workflow/references/` 那份是唯一權威，
**只改這份**；`feature-workflow` 那份一律視為同步產物，不要直接編輯。

改完共用 reference 後，跑一次同步腳本把權威份同步到 feature-workflow：

```bash
./scripts/sync-shared-refs.sh          # 以 bug-workflow 為準同步到 feature-workflow
./scripts/sync-shared-refs.sh --check  # push 前檢查是否一致（不修改）
```

除 reference 外，**共用 script**（`scripts/crew-state.py`，權威同樣在 bug-workflow）
也走這支腳本同步；目標目錄不存在會自動建立。

> **兩者嚴格度不同**：`sync-shared-refs.sh --check` 在「權威份存在但同步副本缺失」時
> 會 exit 1（提醒你跑一次同步）；CI 的 `check-shared-refs.py` 對共用 script 只在
> **兩份都存在且內容不同**時才 fail，缺檔一律優雅跳過（重構期間 script 還在實作中，
> 不該擋 CI）。所以本地 `--check` 紅、CI 綠是預期組合，修法就是跑一次不帶參數的同步。

CI 的 `shared-refs-consistency` job（`scripts/check-shared-refs.py`）仍用 sha256
強制兩份一致，是最後防線：忘了跑同步腳本、或誤改了 feature-workflow 那份，都會被 CI block。
