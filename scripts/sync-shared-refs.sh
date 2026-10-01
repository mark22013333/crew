#!/usr/bin/env bash
# sync-shared-refs.sh — 共用 reference 單一來源同步（C9）
#
# 背景（見 docs/adr/004-shared-ref-duplication.md）：
#   為維持「plugin 可獨立安裝」核心契約，6 個共用 reference 在兩個 plugin
#   各存一份實體副本。ADR 004 選擇「雙份 + CI sha256 防漂移」，唯一負面是
#   「更新時要手動 cp 一次」。本腳本確立 bug-workflow/references/ 為單一
#   權威來源，單向同步到 feature-workflow，把手動 cp 升級為一鍵/可檢查機制。
#
# 為何 bug-workflow 為權威：
#   共用檔中 prerequisites.md、db-templates.md 原生於 bug-workflow，
#   且 bug-workflow 是較基礎的 plugin（crew-init 由其提供）。統一以它為準，
#   feature-workflow 那份一律視為同步產物，開發者只改 bug-workflow 那份。
#
# 用法：
#   ./scripts/sync-shared-refs.sh            # 以 bug-workflow 為準同步到 feature-workflow
#   ./scripts/sync-shared-refs.sh --check    # 只檢查是否一致（CI / push 前用），不修改
#   ./scripts/sync-shared-refs.sh -h | --help

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 共用檔清單（權威 = bug-workflow）。與 scripts/check-shared-refs.py 的清單一致。
SHARED_FILES=(
  prerequisites.md
  db-templates.md
  discipline-preamble.md
  notion-backend.md
  state-discipline.md
  model-policy.md
  host-capabilities.md
  model-routing.json
  config-contract.md
  intake-refinement.md
)
SRC_DIR="$REPO_ROOT/plugins/bug-workflow/references"
DST_DIR="$REPO_ROOT/plugins/feature-workflow/references"

# 共用 script 清單（權威 = bug-workflow）。與 scripts/check-shared-refs.py 的
# SHARED_SCRIPTS 一致。路徑相對 plugin root。
# 與共用 reference 的差別：**來源尚未建立時跳過**（script 可能正在實作中），
# 目標目錄不存在則自動 mkdir -p。
SHARED_SCRIPTS=(
  scripts/crew-state.py
  scripts/crew-model-route.py
  scripts/crew-config.py
)
SRC_PLUGIN="$REPO_ROOT/plugins/bug-workflow"
DST_PLUGIN="$REPO_ROOT/plugins/feature-workflow"

usage() {
  cat <<'EOF'
用法：
  sync-shared-refs.sh            # 以 bug-workflow 為權威，同步共用 reference 與 script 到 feature-workflow
  sync-shared-refs.sh --check    # 僅檢查兩份是否一致（不修改；不一致 exit 1，CI / push 前用）
  sync-shared-refs.sh -h | --help

權威來源：plugins/bug-workflow/（只改這份，改完跑本腳本同步）
同步目標：plugins/feature-workflow/
共用 reference：prerequisites.md、db-templates.md、discipline-preamble.md、notion-backend.md、state-discipline.md、model-policy.md、host-capabilities.md、model-routing.json、config-contract.md、intake-refinement.md
共用 script：scripts/crew-state.py、scripts/crew-model-route.py、scripts/crew-config.py（來源尚未建立時跳過；目標目錄自動 mkdir -p）
EOF
}

CHECK=0
case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  --check)   CHECK=1 ;;
  "")        ;;
  *)         echo "❌ 未知參數：$1"; echo; usage; exit 2 ;;
esac

fail=0
changed=0
for f in "${SHARED_FILES[@]}"; do
  src="$SRC_DIR/$f"
  dst="$DST_DIR/$f"
  [ -f "$src" ] || { echo "❌ 權威檔不存在：$src"; exit 1; }

  # 目標檔不存在＝新增或改名的共用檔。同步模式下直接建立（權威檔存在就足以確認不是筆誤）；
  # --check 模式回報缺失並失敗，行為與下方 SHARED_SCRIPTS 迴圈一致。
  if [ ! -f "$dst" ]; then
    if [ "$CHECK" -eq 1 ]; then
      echo "❌ 缺失：${f}（feature-workflow 尚未有同步副本）"
      fail=1
      continue
    fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "🆕 已建立：$f"
    changed=$((changed + 1))
    continue
  fi

  if cmp -s "$src" "$dst"; then
    [ "$CHECK" -eq 1 ] && echo "✅ 一致：$f"
  elif [ "$CHECK" -eq 1 ]; then
    echo "❌ 不一致：${f}（feature-workflow 那份與權威 bug-workflow 不同）"
    fail=1
  else
    cp "$src" "$dst"
    echo "🔄 已同步：$f"
    changed=$((changed + 1))
  fi
done

# --- 共用 script（容忍來源尚未建立；目標目錄自動建立）------------------------
for s in "${SHARED_SCRIPTS[@]}"; do
  src="$SRC_PLUGIN/$s"
  dst="$DST_PLUGIN/$s"

  if [ ! -f "$src" ]; then
    echo "⏭️  跳過：${s}（權威副本尚未建立，實作中）"
    continue
  fi

  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    [ "$CHECK" -eq 1 ] && echo "✅ 一致：${s}"
    continue
  fi

  if [ "$CHECK" -eq 1 ]; then
    if [ -f "$dst" ]; then
      echo "❌ 不一致：${s}（feature-workflow 那份與權威 bug-workflow 不同）"
    else
      echo "❌ 缺失：${s}（feature-workflow 尚未有同步副本）"
    fi
    fail=1
    continue
  fi

  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "🔄 已同步：$s"
  changed=$((changed + 1))
done

if [ "$CHECK" -eq 1 ]; then
  if [ "$fail" -eq 1 ]; then
    echo
    echo "修法：只改 plugins/bug-workflow/ 那份（references/ 或 scripts/），再跑 ./scripts/sync-shared-refs.sh 同步。"
    exit 1
  fi
  echo "共用 reference 與 script 全部一致。"
  exit 0
fi

if [ "$changed" -eq 0 ]; then
  echo "共用 reference 已一致，無需同步。"
else
  echo "同步完成：$changed 個檔案自 bug-workflow 更新到 feature-workflow。"
  echo "請 git add 這些變更並一起 commit。"
fi
