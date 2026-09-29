# Merge 引導（Feature Branch → DEV）

`/bug-close` 結案前，若偵測到修復在 feature branch 上進行，引導使用者 merge 回開發分支。

---

## 判斷條件

同時滿足以下三項才觸發：

1. **當前分支是 Bug 的修復分支**：`git branch --show-current` = Bug Notion 頁面的「修復分支」欄位
2. **當前分支是 feature/hotfix 分支**（非 DEV/PRD）：不匹配專案設定中的 `dev_branch`、`uat_branch`、`prod_branch`
3. **能取得 DEV 分支名稱**：從 feature-workflow 的 `projects/{repo-id}.md` 讀取 `dev_branch` 欄位

> `dev_branch` 取得方式：先沿用 `/project-add` 規則由 Git remote 解析 `{repo-id}`，再執行：
>
> ```bash
> CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
> python3 "${CREW_PLUGIN_ROOT}/scripts/crew-config.py" resolve \
>   --key feature/project \
>   --repo-id "{repo-id}" \
>   --mode read \
>   --format json
> ```
>
> - `representation=hierarchical` → 從 project frontmatter 讀 `dev_branch`
> - `representation=legacy_monolith` → 沿用舊設定表格 parser，以 repo-id 找專案列
> - `source=missing` 或沒有 `dev_branch` → 視為條件 3 不成立，使用下方簡化提示
>
> Consumer 不得自行拼 Host-specific project config path。

---

## 互動式引導

```
📋 結案前分支合併

當前在 feature/sample-fix
目標 DEV 分支：ORG01P2401_DEV

要合併回 DEV 嗎？
  1. 是，merge --no-ff 並繼續結案
  2. 否，我稍後自己合併
  3. 已經合併過了，直接結案
```

---

## 選 1：執行 Merge

1. 檢查工作區乾淨：`git status --porcelain`
   - 有未提交變更 → 提示先 commit 或 stash，暫停
2. 切換到 DEV：`git checkout {dev_branch}`
3. 拉取最新：`git pull`（若有 remote tracking）
4. 合併：`git merge {feature_branch} --no-ff`
   - 成功 → 繼續結案流程
   - 衝突 → 顯示衝突檔案列表，暫停結案，提示使用者解決衝突後重新執行 `/bug-close`
5. **不自動 push**，在結案結果中提示：`git push origin {dev_branch}`

---

## 選 2 或 3：跳過 Merge

直接進入原有的結案流程。

---

## 條件不滿足時

- 當前不在修復分支 → 跳過
- 當前在 DEV/PRD 分支 → 跳過
- `dev_branch` 未設定 → 顯示簡化提示：
  ```
  💡 目前在 feature branch，結案後記得 merge 回開發分支。
     若要啟用自動 merge 引導，請在專案設定中新增 dev_branch。
  ```
