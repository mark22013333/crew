#!/usr/bin/env python3
"""Lint plugin.json / marketplace.json 的宣告是否與實際檔案相符。

存在的理由：
  其餘 lint 腳本（lint-skills.py、lint-readme-sync.py、lint-skill-contract.py）
  一律以「掃 plugins/*/skills/*/ 實際目錄」為基準，沒有任何一支比對
  plugin.json 的 skills 陣列，因此「陣列與目錄不一致」是 CI 的檢查盲區。
  feature-workflow@5.0.0 刪掉 plan-spec / plan-db / plan-arch 三個目錄卻沒同步
  陣列，導致 Claude Code 載入時報 `skills path not found`，該問題存活 37 天
  （2026-07-28 → 2026-09-03）都沒被 CI 攔下。本腳本補上這個維度。

檢查項目（全部 fail，無警告級）：
  1. skills 陣列宣告的路徑，實際目錄不存在
  2. skills/ 下實際存在的目錄，未被 skills 陣列宣告
  3. skills 陣列有重複宣告
  4. 宣告的 skill 目錄缺少 SKILL.md 或其內容為空
  5. hooks 欄位指向的檔案不存在
  6. marketplace.json 的 source 目錄不存在，或與 plugins/ 下實際 plugin 未一一對應
  7. hooks 欄位宣告標準路徑 hooks/hooks.json（該檔會自動載入，重複宣告會讓
     Claude Code 報 Duplicate hooks file detected，整份 hook 因此完全不載入；
     manifest 的 hooks 只該引用額外的 hook 檔案）

退出碼：
  0 = 無錯誤
  1 = 有錯誤
"""

import json
import posixpath
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO / "plugins"
MARKETPLACE_JSON = REPO / ".claude-plugin" / "marketplace.json"
CODEX_MARKETPLACE_JSON = REPO / ".agents" / "plugins" / "marketplace.json"
PORTABLE_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
STANDARD_HOOKS = "hooks/hooks.json"


def lint_plugin(plugin_dir: Path, errors: list[str]) -> int:
    """檢查單一 plugin 的 manifest，回傳檢查過的 skill 宣告數。"""
    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    rel = manifest.relative_to(REPO)

    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: JSON 解析失敗 —— {exc}")
        return 0

    declared = data.get("skills", [])
    if not isinstance(declared, list):
        errors.append(f"{rel}: skills 欄位必須是陣列")
        return 0

    # 1 + 4：宣告的路徑要存在，且要有非空 SKILL.md
    for entry in declared:
        target = plugin_dir / entry
        if not target.is_dir():
            errors.append(
                f"{rel}: skills 宣告 `{entry}` 但目錄不存在"
                f"（Claude Code 載入時會報 skills path not found）"
            )
            continue
        skill_md = target / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"{rel}: `{entry}` 缺少 SKILL.md")
        elif not skill_md.read_text(encoding="utf-8").strip():
            errors.append(f"{rel}: `{entry}/SKILL.md` 內容為空")

    declared_names = [entry.rstrip("/").split("/")[-1] for entry in declared]

    # 2：實際存在但未宣告
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for child in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            if child.name not in declared_names:
                errors.append(
                    f"{rel}: `skills/{child.name}/` 實際存在但 skills 陣列未宣告"
                )

    # 3：重複宣告
    for name in sorted(set(declared_names)):
        count = declared_names.count(name)
        if count > 1:
            errors.append(f"{rel}: skills 陣列重複宣告 `{name}` {count} 次")

    # 5 + 7：hooks 宣告
    hooks = data.get("hooks")
    if isinstance(hooks, str):
        entries = [hooks]
    elif isinstance(hooks, list):
        entries = [e for e in hooks if isinstance(e, str)]
    else:
        entries = []

    for entry in entries:
        if posixpath.normpath(entry) == STANDARD_HOOKS:
            errors.append(
                f"{rel}: hooks 不可宣告標準路徑 `{entry}` —— "
                f"`{STANDARD_HOOKS}` 會被自動載入，再宣告一次會讓 Claude Code 報 "
                f"Duplicate hooks file detected 並整份 hook 載入失敗；"
                f"manifest 的 hooks 只該引用額外的 hook 檔案"
            )
        elif not (plugin_dir / entry).is_file():
            errors.append(f"{rel}: hooks 宣告 `{entry}` 但檔案不存在")

    return len(declared)


def lint_marketplace(plugin_dirs: list[Path], errors: list[str]) -> None:
    """檢查 marketplace.json 的 source 與 plugins/ 一一對應。"""
    rel = MARKETPLACE_JSON.relative_to(REPO)
    try:
        data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: JSON 解析失敗 —— {exc}")
        return

    listed: set[str] = set()
    for entry in data.get("plugins", []):
        source = entry.get("source", "")
        target = (REPO / source).resolve() if source else None
        if target is None or not target.is_dir():
            errors.append(
                f"{rel}: plugin `{entry.get('name')}` 的 source `{source}` 目錄不存在"
            )
            continue
        listed.add(target.name)

    actual = {d.name for d in plugin_dirs}
    for name in sorted(actual - listed):
        errors.append(f"{rel}: `plugins/{name}/` 存在但 marketplace.json 未列出")
    for name in sorted(listed - actual):
        errors.append(f"{rel}: marketplace.json 列出 `{name}` 但 plugins/ 下無此目錄")



def lint_portable_manifest(plugin_dir: Path, errors: list[str]) -> None:
    """檢查 Agent Plugins portable manifest 與 Claude manifest 版本/名稱一致。"""
    portable = plugin_dir / "plugin.json"
    claude = plugin_dir / ".claude-plugin" / "plugin.json"
    rel = portable.relative_to(REPO)

    if not portable.is_file():
        errors.append(f"{plugin_dir.relative_to(REPO)}: 缺少 portable plugin.json")
        return

    try:
        pdata = json.loads(portable.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: JSON 解析失敗 —— {exc}")
        return

    try:
        cdata = json.loads(claude.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return  # Claude manifest 的解析錯誤已由 lint_plugin 回報

    if pdata.get("$schema") != PORTABLE_SCHEMA:
        errors.append(
            f"{rel}: $schema 必須是 {PORTABLE_SCHEMA}"
        )
    if pdata.get("name") != plugin_dir.name:
        errors.append(
            f"{rel}: name={pdata.get('name')!r}，應與目錄名 {plugin_dir.name!r} 一致"
        )
    if pdata.get("name") != cdata.get("name"):
        errors.append(
            f"{rel}: portable name 與 .claude-plugin/plugin.json 不一致"
        )
    if pdata.get("version") != cdata.get("version"):
        errors.append(
            f"{rel}: portable version={pdata.get('version')} 與 Claude manifest "
            f"version={cdata.get('version')} 不一致"
        )
    if not pdata.get("description"):
        errors.append(f"{rel}: 缺少 description")


def lint_codex_marketplace(plugin_dirs: list[Path], errors: list[str]) -> None:
    """檢查 Codex repo marketplace 的 local source 與 plugins/ 一一對應。"""
    rel = CODEX_MARKETPLACE_JSON.relative_to(REPO)
    if not CODEX_MARKETPLACE_JSON.is_file():
        errors.append(f"{rel}: 檔案不存在")
        return

    try:
        data = json.loads(CODEX_MARKETPLACE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: JSON 解析失敗 —— {exc}")
        return

    if not data.get("name"):
        errors.append(f"{rel}: 缺少 marketplace name")

    listed: set[str] = set()
    for entry in data.get("plugins", []):
        name = entry.get("name")
        source = entry.get("source")
        if isinstance(source, str):
            source_path = source
        elif isinstance(source, dict):
            if source.get("source") != "local":
                errors.append(
                    f"{rel}: plugin {name!r} repo marketplace 預期 source=local"
                )
            source_path = source.get("path", "")
        else:
            source_path = ""

        if not isinstance(source_path, str) or not source_path.startswith("./"):
            errors.append(
                f"{rel}: plugin {name!r} 的 source.path 必須是 ./ 開頭的相對路徑"
            )
            continue

        target = (REPO / source_path).resolve()
        if not target.is_dir():
            errors.append(
                f"{rel}: plugin {name!r} 的 source.path {source_path!r} 目錄不存在"
            )
            continue
        if name != target.name:
            errors.append(
                f"{rel}: plugin name={name!r} 與 source 目錄 {target.name!r} 不一致"
            )
        listed.add(target.name)

        policy = entry.get("policy", {})
        if not policy.get("installation"):
            errors.append(f"{rel}: plugin {name!r} 缺少 policy.installation")
        if not policy.get("authentication"):
            errors.append(f"{rel}: plugin {name!r} 缺少 policy.authentication")
        if not entry.get("category"):
            errors.append(f"{rel}: plugin {name!r} 缺少 category")

    actual = {d.name for d in plugin_dirs}
    for name in sorted(actual - listed):
        errors.append(f"{rel}: plugins/{name}/ 存在但 Codex marketplace 未列出")
    for name in sorted(listed - actual):
        errors.append(f"{rel}: Codex marketplace 列出 {name!r} 但 plugins/ 下無此目錄")

def main() -> int:
    errors: list[str] = []
    plugin_dirs = sorted(
        d for d in PLUGINS_DIR.iterdir()
        if d.is_dir() and (d / ".claude-plugin" / "plugin.json").is_file()
    )

    total_skills = 0
    for plugin_dir in plugin_dirs:
        total_skills += lint_plugin(plugin_dir, errors)
        lint_portable_manifest(plugin_dir, errors)

    lint_marketplace(plugin_dirs, errors)
    lint_codex_marketplace(plugin_dirs, errors)

    for e in errors:
        print(f"❌ {e}")

    if errors:
        print(f"\n檢查 {len(plugin_dirs)} 個 plugin manifest：{len(errors)} 錯誤")
        return 1

    print(
        f"✅ 檢查 {len(plugin_dirs)} 個 Claude + portable plugin manifest、"
        f"{total_skills} 個 skill 宣告，與實際檔案完全相符"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
