#!/usr/bin/env bash
# bump-version.sh — 版本同步腳本
#
# 一次同步 plugin 版本到四處：
#   1. plugins/<plugin>/.claude-plugin/plugin.json
#   2. plugins/<plugin>/plugin.json（Agent Plugins portable manifest）
#   3. .claude-plugin/marketplace.json
#   4. plugins/<plugin>/README.md（第一行 vX.Y.Z）
#
# 另支援 --check 模式：僅檢查不修改，CI 用。
#
# 為何需要此腳本：
#   CONTRIBUTING.md 明確警告「只改 README 不改 plugin.json 是易錯點」，
#   實際也發生過 marketplace.json 落後 plugin.json 9 個 minor。
#   此腳本將易錯的手動同步轉為一行指令。
#
# 用法：
#   ./scripts/bump-version.sh <plugin> <new_version>   # 同步版本
#   ./scripts/bump-version.sh --check                  # 僅檢查一致性
#   ./scripts/bump-version.sh -h | --help

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
用法：
  bump-version.sh <plugin> <new_version>     # 同步版本到三處
  bump-version.sh --check                    # 僅檢查四處一致性（CI 用）
  bump-version.sh -h | --help

範例：
  bump-version.sh feature-workflow 4.18.0
  bump-version.sh bug-workflow 3.9.0
  bump-version.sh --check

備註：
  CHANGELOG.md header 不自動處理（內容由人決定）。
  本腳本完成後請手動在 CHANGELOG.md 頂端新增：
    ## [<plugin>@<version>] - <YYYY-MM-DD>
EOF
}

validate_semver() {
  local v="$1"
  if [[ ! "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "❌ 版本必須為 semver 格式 X.Y.Z（你給的：$v）" >&2
    exit 1
  fi
}

get_plugin_json_version() {
  local plugin="$1"
  python3 -c "
import json
with open('$REPO_ROOT/plugins/$plugin/.claude-plugin/plugin.json') as f:
    print(json.load(f)['version'])
"
}

get_portable_json_version() {
  local plugin="$1"
  python3 -c "
import json
with open('$REPO_ROOT/plugins/$plugin/plugin.json') as f:
    print(json.load(f)['version'])
"
}

get_marketplace_version() {
  local plugin="$1"
  python3 -c "
import json
with open('$REPO_ROOT/.claude-plugin/marketplace.json') as f:
    data = json.load(f)
for p in data['plugins']:
    if p['name'] == '$plugin':
        print(p['version'])
        break
"
}

get_readme_version() {
  local plugin="$1"
  head -1 "$REPO_ROOT/plugins/$plugin/README.md" \
    | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' \
    | head -1 \
    | sed 's/^v//'
}

set_plugin_json_version() {
  local plugin="$1"
  local version="$2"
  python3 - <<PYEOF
import json
path = '$REPO_ROOT/plugins/$plugin/.claude-plugin/plugin.json'
with open(path) as f:
    data = json.load(f)
data['version'] = '$version'
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
PYEOF
}

set_portable_json_version() {
  local plugin="$1"
  local version="$2"
  python3 - <<PYEOF
import json
path = '$REPO_ROOT/plugins/$plugin/plugin.json'
with open(path) as f:
    data = json.load(f)
data['version'] = '$version'
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
PYEOF
}

set_marketplace_version() {
  local plugin="$1"
  local version="$2"
  python3 - <<PYEOF
import json
path = '$REPO_ROOT/.claude-plugin/marketplace.json'
with open(path) as f:
    data = json.load(f)
for p in data['plugins']:
    if p['name'] == '$plugin':
        p['version'] = '$version'
        break
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
PYEOF
}

set_readme_version() {
  local plugin="$1"
  local version="$2"
  python3 - <<PYEOF
import re
path = '$REPO_ROOT/plugins/$plugin/README.md'
with open(path) as f:
    lines = f.readlines()
lines[0] = re.sub(r'v\d+\.\d+\.\d+', 'v$version', lines[0])
with open(path, 'w') as f:
    f.writelines(lines)
PYEOF
}

check_consistency() {
  local rc=0
  for plugin in bug-workflow feature-workflow; do
    local cv pv mv rv
    cv=$(get_plugin_json_version "$plugin")
    pv=$(get_portable_json_version "$plugin")
    mv=$(get_marketplace_version "$plugin")
    rv=$(get_readme_version "$plugin")

    if [[ "$cv" == "$pv" && "$pv" == "$mv" && "$mv" == "$rv" ]]; then
      echo "✅ $plugin: $cv"
    else
      echo "❌ $plugin 版本不一致："
      echo "   .claude-plugin/plugin.json: $cv"
      echo "   portable plugin.json:       $pv"
      echo "   marketplace.json:           $mv"
      echo "   README.md:                  $rv"
      rc=1
    fi
  done
  return $rc
}

bump_version() {
  local plugin="$1"
  local version="$2"

  if [[ ! -d "$REPO_ROOT/plugins/$plugin" ]]; then
    echo "❌ Plugin 不存在：$plugin" >&2
    echo "可用：$(ls "$REPO_ROOT/plugins" | tr '\n' ' ')" >&2
    exit 1
  fi

  validate_semver "$version"

  local old_pv
  old_pv=$(get_plugin_json_version "$plugin")
  echo "🔄 $plugin: $old_pv → $version"

  set_plugin_json_version "$plugin" "$version"
  set_portable_json_version "$plugin" "$version"
  set_marketplace_version "$plugin" "$version"
  set_readme_version "$plugin" "$version"

  echo ""
  echo "✅ 已同步四處版本："
  echo "   plugins/$plugin/.claude-plugin/plugin.json"
  echo "   plugins/$plugin/plugin.json"
  echo "   .claude-plugin/marketplace.json"
  echo "   plugins/$plugin/README.md"
  echo ""
  echo "⚠️  CHANGELOG.md 仍需手動新增 header："
  echo "   ## [$plugin@$version] - $(date +%Y-%m-%d)"
  echo ""

  check_consistency
}

main() {
  case "${1:-}" in
    -h|--help|"")
      usage
      exit 0
      ;;
    --check)
      check_consistency
      ;;
    *)
      if [[ $# -ne 2 ]]; then
        usage
        exit 1
      fi
      bump_version "$1" "$2"
      ;;
  esac
}

main "$@"
