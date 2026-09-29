# verify-docx-cli

Plugin 內建 .NET 子專案，將 `verify.md` 渲染為品牌 Word 驗收報告。

## 為什麼自帶？

- 不依賴 minimax-skills 的 CLI（避免 upstream CLI 變動風險）
- ProjectReference 共用 `MiniMaxAIDocx.Core` 的 OpenXML helper
- 結構驗證用 OpenXML SDK 的 `OpenXmlValidator`

## 環境需求

- .NET SDK 8.0+（9.x / 10.x 也支援，靠 `RollForward=LatestMajor`）
- minimax-skills plugin 已安裝，或以 `MinimaxCorePath` 指向 `MiniMaxAIDocx.Core.csproj`

## Build & Run

不要假設 plugin 一定裝在某個 Host marketplace 目錄。先用 CREW 的 plugin-root contract：

```bash
CREW_PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
cd "${CREW_PLUGIN_ROOT}/references/dotnet/verify-docx-cli"

dotnet run --framework net8.0 -- \
  --verify ../../path/to/verify.md \
  --output /tmp/report.docx \
  --style intumit \
  --cover '{"project":"X","feature":"Y","author":"Z","date":"2026-05-26","company":"Intumit","version":"v1.0"}'
```

若 `CREW_PLUGIN_ROOT` 為空，應由呼叫端明確傳入 plugin root，不要猜安裝路徑。

本專案 multi-target（`net8.0;net10.0`），`dotnet run` 必須指定 `--framework`。

完整參數：

| 參數 | 必填 | 說明 |
|------|-----|------|
| `--verify` | ✓ | verify.md 路徑 |
| `--output` | ✓ | 輸出 docx 路徑 |
| `--cover` | ✓ | 封面資訊 JSON |
| `--style` | | `intumit`（預設）/ `tech-dark` / `swiss` |
| `--logo` | | 覆寫 logo path |
| `--screenshots` | | 截圖目錄 |
| `--evidence` | | evidence 目錄 |

退出碼：成功且結構驗證通過 → `0`；docx 已產出但 validator 失敗 → `1`。

## MinimaxCorePath

`VerifyDocxCli.csproj` 的現行 fallback 仍是 Claude Code adapter 的 minimax-skills marketplace cache。跨 Host 使用時，建議明確設定：

```bash
export MinimaxCorePath=/absolute/path/to/MiniMaxAIDocx.Core.csproj
dotnet run --framework net8.0 -- ...
```

| 變數 | 用途 |
|------|------|
| `MinimaxCorePath` | MiniMaxAIDocx.Core.csproj 絕對路徑 |

> 這個 fallback 是 verify-docx-cli/minimax integration 的 Host-specific 相容層，不是 CREW portable config contract。

## Logo 偵測

CLI 依序檢查：

1. `--logo {path}`
2. Claude Code adapter 的既有 user override：`$HOME/.claude/feature-workflow/assets/intumit-logo.png`
3. `{plugin}/references/dotnet/verify-docx-cli/assets/intumit-logo.png`

跨 Host 最穩定的方式是傳 `--logo`，或使用 plugin 內建 asset。現行第 2 層是歷史 Claude adapter fallback。

`--style swiss` 不需要 logo；其他 style 三層都找不到時會拋出 `FileNotFoundException`。

## 渲染特性

- **TOC field**：插入 TOC field + `UpdateFieldsOnOpen`
- **敏感資訊遮蔽**：Cookie / Authorization / API key 等自動遮蔽
- **長回應截斷**：API response 過長時切首尾並引用 evidence
- **截圖**：依 `--screenshots` 嵌入；缺檔不阻擋整份報告

## 開發

| 加什麼 | 改哪 |
|--------|------|
| 新 brand style | `Styles/` + `BrandStyleFactory.Resolve` |
| 新段落 | `Markdown/` parser + `Rendering/` renderer |

## 已知限制

- `MinimaxCorePath` 預設 fallback 與 user logo override 仍保留 Claude Code adapter 路徑；portable 呼叫應用 env / CLI 參數覆寫。
- 未完整測試 Windows 路徑差異。
- 無單元測試，僅 smoke test。
