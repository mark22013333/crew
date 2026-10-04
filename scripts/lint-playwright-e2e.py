#!/usr/bin/env python3
"""Static policy lint for Playwright E2E candidates produced by plan-verify.

This is intentionally heuristic: it catches promotion blockers that are cheap and
safe to detect from source text. Runtime stability / cleanup correctness still
belongs to the E2E promotion phase.

Usage:
  python3 scripts/lint-playwright-e2e.py tests/foo.spec.ts
  python3 scripts/lint-playwright-e2e.py tests/ --strict-review
  python3 scripts/lint-playwright-e2e.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SPEC_SUFFIXES = (".spec.js", ".spec.ts", ".spec.mjs", ".spec.cjs")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: Path
    line: int
    message: str


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def add_matches(
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    path: Path,
    text: str,
    pattern: str,
    message: str,
    flags: int = 0,
) -> None:
    for match in re.finditer(pattern, text, flags):
        issues.append(Issue(severity, code, path, line_of(text, match.start()), message))


def lint_text(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []

    hard_rules = (
        ("TEST_ONLY", r"\btest\s*\.\s*only\s*\(", "CI candidate 不得含 test.only"),
        ("UNRESOLVED_MARKER", r"\b(?:TODO|FIXME)\b", "CI candidate 不得保留 TODO/FIXME"),
        (
            "EMPTY_SKIP",
            r"\btest\s*\.\s*(?:skip|fixme)\s*\(\s*\)",
            "test.skip()/test.fixme() 必須有明確 contract，不能空白略過",
        ),
        (
            "ABSOLUTE_HOME_PATH",
            r"(?:/Users/[^/\s'\"]+|/home/[^/\s'\"]+|[A-Za-z]:\\\\Users\\\\[^\\\s'\"]+)",
            "不得依賴某位工程師家目錄的絕對路徑",
        ),
        (
            "HARDCODED_SECRET",
            r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\b\s*[:=]\s*['\"][^'\"$\{<][^'\"]{2,}['\"]",
            "疑似把 credential/token/secret 直接寫進測試",
        ),
    )
    for code, pattern, message in hard_rules:
        add_matches(
            issues,
            severity="HARD",
            code=code,
            path=path,
            text=text,
            pattern=pattern,
            message=message,
        )

    if not re.search(r"\bAC-\d+\b", text):
        issues.append(Issue("HARD", "MISSING_AC", path, 1, "找不到 AC-n mapping；candidate 必須能回連驗收條件"))

    if not re.search(r"\bexpect\s*\(", text):
        issues.append(Issue("HARD", "MISSING_ASSERTION", path, 1, "找不到 Playwright expect assertion；只操作/截圖不能 promotion"))

    if not re.search(r"[A-Za-z0-9][A-Za-z0-9._-]*#AC-\d+\b", text):
        issues.append(
            Issue(
                "REVIEW",
                "WEAK_AC_JOIN_KEY",
                path,
                1,
                "只有 AC-n 而沒有 {slug}#AC-n 穩定 join key；請確認 reporter/annotation 有提供 slug",
            )
        )

    review_rules = (
        ("FIXED_SLEEP", r"\.waitForTimeout\s*\(", "固定 sleep 需說明為何不能改成可觀察條件"),
        ("XPATH", r"(?:xpath=|locator\s*\(\s*['\"]//)", "XPath 對 DOM 重構較脆弱，promotion 前需審查"),
        ("NTH_CHILD", r":nth-child\s*\(", "nth-child locator 對 DOM 結構高度敏感"),
        (
            "HARDCODED_LOCAL_URL",
            r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?",
            "hardcoded local URL 應改由 baseURL/profile/環境變數提供",
        ),
        ("FIXED_RECORD_ID", r"(?:[?&](?:id|templateId|scheduleId)=)\d+\b", "固定資料 ID 需有 fixture contract"),
        (
            "SKIP_OR_FIXME",
            r"\btest\s*\.\s*(?:skip|fixme)\s*\(",
            "skip/fixme 需要明確 reason，且 CI-required AC 不得被靜默略過",
        ),
    )
    for code, pattern, message in review_rules:
        add_matches(
            issues,
            severity="REVIEW",
            code=code,
            path=path,
            text=text,
            pattern=pattern,
            message=message,
        )

    return _dedupe(issues)


def _dedupe(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, str, Path, int]] = set()
    result: list[Issue] = []
    for issue in issues:
        key = (issue.severity, issue.code, issue.path, issue.line)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def collect_files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(path)
            continue
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.name.endswith(SPEC_SUFFIXES):
                    found.append(candidate)
            continue
        raise FileNotFoundError(raw)
    return sorted(set(found))


def run_lint(paths: list[str], strict_review: bool) -> int:
    files = collect_files(paths)
    if not files:
        print("❌ 找不到 Playwright spec 檔案")
        return 2

    issues: list[Issue] = []
    for path in files:
        issues.extend(lint_text(path, path.read_text(encoding="utf-8")))

    for issue in sorted(issues, key=lambda x: (str(x.path), x.line, x.severity, x.code)):
        icon = "❌" if issue.severity == "HARD" else "⚠️"
        print(f"{icon} {issue.severity} {issue.path}:{issue.line} [{issue.code}] {issue.message}")

    hard = sum(1 for issue in issues if issue.severity == "HARD")
    review = sum(1 for issue in issues if issue.severity == "REVIEW")
    print(f"\nPlaywright E2E policy：{len(files)} 檔，HARD={hard}，REVIEW={review}")

    if hard > 0 or (strict_review and review > 0):
        return 1
    return 0


def self_test() -> int:
    good = """
const { test, expect } = require('@playwright/test');
test('feature-x#AC-1 query', async ({ page }) => {
  await test.step('AC-1: query', async () => {
    await expect(page.getByRole('main')).toBeVisible();
  });
});
""".strip()

    bad = """
const { test } = require('@playwright/test');
// TODO remove local shortcut
const password = 'plain-secret';
const repo = '/Users/alice/IdeaProjects/private-e2e';
test.only('AC-1', async ({ page }) => {
  await page.goto('/x');
});
""".strip()

    review = """
const { test, expect } = require('@playwright/test');
test('feature-y#AC-2 flow', async ({ page }) => {
  await page.goto('http://localhost:8080/x?id=5');
  await page.locator('div:nth-child(2)').click();
  await page.waitForTimeout(500);
  await expect(page.getByText('ok')).toBeVisible();
});
""".strip()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        good_path = root / "good.spec.js"
        bad_path = root / "bad.spec.js"
        review_path = root / "review.spec.js"

        good_issues = lint_text(good_path, good)
        bad_issues = lint_text(bad_path, bad)
        review_issues = lint_text(review_path, review)

        assert not [i for i in good_issues if i.severity == "HARD"], good_issues
        assert len([i for i in bad_issues if i.severity == "HARD"]) >= 4, bad_issues
        assert not [i for i in review_issues if i.severity == "HARD"], review_issues
        review_codes = {i.code for i in review_issues if i.severity == "REVIEW"}
        assert {"FIXED_SLEEP", "NTH_CHILD", "HARDCODED_LOCAL_URL", "FIXED_RECORD_ID"} <= review_codes, review_codes

    print("✅ lint-playwright-e2e self-test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint Playwright E2E candidates for CREW CI promotion")
    parser.add_argument("paths", nargs="*", help="spec file or directory")
    parser.add_argument("--strict-review", action="store_true", help="REVIEW issue 也回傳 exit 1")
    parser.add_argument("--self-test", action="store_true", help="執行內建 regression tests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        return self_test()
    if not args.paths:
        print("❌ 請指定 spec file/directory，或使用 --self-test")
        return 2
    try:
        return run_lint(args.paths, args.strict_review)
    except (OSError, UnicodeError) as exc:
        print(f"❌ 無法讀取測試檔：{exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
