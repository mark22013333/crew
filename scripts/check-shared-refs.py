#!/usr/bin/env python3
"""檢查兩個 plugin 的共用 reference／script 檔案沒有漂移。

bug-workflow 與 feature-workflow 各自帶一份 prerequisites.md / db-templates.md
（為了 plugin 可獨立安裝），用 sha256 強制兩份完全一致，否則 CI fail。

當其中一份要更新時，正確做法是同時改兩份；本檢查防止漏改。

共用 script（SHARED_SCRIPTS）同理：權威副本在 bug-workflow，同步一份到
feature-workflow 以維持「plugin 可獨立安裝」契約。與 reference 的差別是
**尚未存在時優雅跳過**——這些 script 可能正在實作中，缺檔不算漂移。

退出碼：
  0 = 所有共用 reference 在兩 plugin 中內容一致（共用 script 一致或尚未建立）
  1 = 任一份漂移或缺失
"""

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SHARED_REFS = [
    "references/prerequisites.md",
    "references/db-templates.md",
    "references/discipline-preamble.md",
    "references/notion-backend.md",
    "references/state-discipline.md",
    "references/model-policy.md",
    "references/host-capabilities.md",
    "references/model-routing.json",
    "references/config-contract.md",
]

# 共用 script（權威 = bug-workflow，同步到 feature-workflow）。
# 與 SHARED_REFS 的差別：**尚未存在時優雅跳過，不視為漂移**（script 可能正在實作中）。
# 與 scripts/sync-shared-refs.sh 的 SHARED_SCRIPTS 清單一致。
SHARED_SCRIPTS = [
    "scripts/crew-state.py",
    "scripts/crew-model-route.py",
    "scripts/crew-config.py",
]

PLUGIN_A = "bug-workflow"
PLUGIN_B = "feature-workflow"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_shared_scripts() -> int:
    """共用 script 的 sha256 一致性；來源或目標任一尚未建立就跳過。"""
    rc = 0
    for script in SHARED_SCRIPTS:
        a = REPO / "plugins" / PLUGIN_A / script
        b = REPO / "plugins" / PLUGIN_B / script

        if not a.exists() and not b.exists():
            print(f"⏭️  {script} 兩 plugin 皆尚未建立，跳過（實作中）")
            continue
        if not a.exists():
            print(f"⏭️  {script} 權威副本（{PLUGIN_A}）尚未建立，跳過（實作中）")
            continue
        if not b.exists():
            print(f"⏭️  {script} 同步副本（{PLUGIN_B}）尚未建立，跳過")
            print(f"   建立方式：./scripts/sync-shared-refs.sh")
            continue

        ha = sha256(a)
        hb = sha256(b)

        if ha == hb:
            print(f"✅ {script} 兩 plugin 內容一致")
        else:
            print(f"❌ {script} 兩 plugin 內容不同：")
            print(f"   {PLUGIN_A:>20}: {ha[:12]}...")
            print(f"   {PLUGIN_B:>20}: {hb[:12]}...")
            print(f"   修法：只改 bug-workflow 那份（權威），再跑 ./scripts/sync-shared-refs.sh 同步")
            rc = 1

    return rc


def main() -> int:
    rc = 0
    for ref in SHARED_REFS:
        a = REPO / "plugins" / PLUGIN_A / ref
        b = REPO / "plugins" / PLUGIN_B / ref

        if not a.exists():
            print(f"❌ 缺失：{a.relative_to(REPO)}")
            rc = 1
            continue
        if not b.exists():
            print(f"❌ 缺失：{b.relative_to(REPO)}")
            rc = 1
            continue

        ha = sha256(a)
        hb = sha256(b)

        if ha == hb:
            print(f"✅ {ref} 兩 plugin 內容一致")
        else:
            print(f"❌ {ref} 兩 plugin 內容不同：")
            print(f"   {PLUGIN_A:>20}: {ha[:12]}...")
            print(f"   {PLUGIN_B:>20}: {hb[:12]}...")
            print(f"   修法：只改 bug-workflow 那份（權威），再跑 ./scripts/sync-shared-refs.sh 同步")
            rc = 1

    rc |= check_shared_scripts()

    return rc


if __name__ == "__main__":
    sys.exit(main())
