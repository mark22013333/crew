---
name: crew-upgrade
description: 更新 CREW plugins（bug-workflow + feature-workflow）並驗證目前版本。當使用者提到 /crew-upgrade、「更新 CREW」、「升級 CREW plugin」時觸發此 Skill。
---

# crew-upgrade — Portable CREW Update

更新目前 Host 中已安裝的 CREW plugins。**只使用 Host 公開 plugin CLI 作為 source of truth**；不得直接讀寫 Host 私有 marketplace cache、installed registry 或設定檔。

## 使用方式

```text
/crew-upgrade
/crew-upgrade --check
/crew-upgrade --changelog
```

- 預設：檢查目前狀態 → 更新 marketplace → 更新/refresh 已安裝 CREW plugins → 再列一次狀態。
- `--check`：只列狀態，不執行任何更新。
- `--changelog`：只顯示/連結 CREW `CHANGELOG.md`，不更新。

## 不變量

1. **不得**讀寫 Host 私有 plugin registry/cache。
2. **不得**使用已退休的 `.claude-company` 路徑。
3. 不因為某個 CLI binary 恰好存在就猜目前 Host；以目前 session/adapter context 判定。若 Host 身分不可靠，先詢問「Claude Code / Codex」。
4. 只更新目前已安裝的 CREW plugin；未安裝的 plugin 不自動加裝。
5. 更新後提醒使用者開新 session，因目前 session 可能仍載入舊 Skill。
6. Host CLI 回報失敗時保留原錯誤，不直接改 cache 檔案繞過。

---

## Adapter A：Claude Code

Marketplace 名稱：`company-marketplace`。

### Check

```bash
claude plugin marketplace list
claude plugin list
```

從 `claude plugin list` 判斷 `bug-workflow` / `feature-workflow` 哪些已安裝；不要解析 Host 私有 registry。

`--check` 到這裡結束。

### Update

先刷新 marketplace：

```bash
claude plugin marketplace update company-marketplace
```

只對 check 階段確認已安裝的 plugin 執行：

```bash
claude plugin update bug-workflow@company-marketplace
claude plugin update feature-workflow@company-marketplace
```

若只安裝其中一個，只執行該行。最後：

```bash
claude plugin list
```

若 marketplace 尚未存在，提示 bootstrap：

```bash
claude plugin marketplace add mark22013333/crew
```

不要自行刪除 marketplace/plugin cache 當成修復手段。

---

## Adapter B：Codex

Marketplace 名稱：`crew`。

### Check

```bash
codex plugin marketplace list
codex plugin list
```

`--check` 到這裡結束。

### Update

```bash
codex plugin marketplace upgrade crew
codex plugin list
```

Codex local marketplace 的 plugin 內容由 marketplace snapshot 提供；refresh 後以 `codex plugin list` 回報的 installed/enabled/version 為準。**不要發明不存在的 Codex plugin-specific update 子命令。**

若 marketplace 尚未存在：

```bash
codex plugin marketplace add mark22013333/crew
```

若某個 plugin 本來就未安裝，預設不要自動安裝；只有使用者明確要求時才執行：

```bash
codex plugin add bug-workflow@crew
codex plugin add feature-workflow@crew
```

---

## --changelog

不要從 Host 私有 marketplace cache 猜 CHANGELOG。優先讀目前 repository checkout 的 `CHANGELOG.md`；若目前不是 CREW repo，提供 canonical URL：

`https://github.com/mark22013333/crew/blob/main/CHANGELOG.md`

若 Host 可安全讀取該 URL，可摘要最近版本；不能存取就只回報 URL，不影響 update 流程。

---

## 完成回報

至少回報 Host、marketplace refresh 結果、兩個 plugin 的 installed/update 狀態，並提醒：

```text
下一步：開新 session，讓新版 Skill / hook 生效。
```

不要把「CLI 指令成功」延伸成「目前 session 已載入新版」。

## 何時不用

- 首次安裝 CREW → 依 README 安裝流程，再跑 `/crew-init`
- 環境健診 → `/crew-doctor`
- 更新其他 plugin → 使用該 plugin/marketplace 自己的更新機制
