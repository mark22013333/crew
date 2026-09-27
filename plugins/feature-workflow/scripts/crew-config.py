#!/usr/bin/env python3
"""Resolve CREW-owned config data by portable logical key.

This script is intentionally side-effect free:
- read: pick the first existing canonical/legacy candidate
- write: return the canonical portable path only
- never mkdir/move/write user files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

KEYS = {
    "feature/config",
    "feature/project",
    "feature/stack",
    "bug/config",
    "bug/learning",
}

SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class ConfigError(Exception):
    pass


def portable_root() -> Path:
    explicit = os.environ.get("CREW_CONFIG_HOME")
    if explicit:
        return Path(explicit).expanduser()

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / "crew"

    return Path.home() / ".config" / "crew"


def safe_leaf(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or not SAFE_FILE_RE.fullmatch(value):
        raise ConfigError(
            f"{label} 必須是安全的單一檔名（A-Z/a-z/0-9/._-），不得包含路徑分隔符：{value!r}"
        )
    return value


def sanitize_repo_id(repo_id: str) -> str:
    value = repo_id.strip().removesuffix(".git")
    if not value:
        raise ConfigError("--repo-id 不可為空")
    if value.startswith(("/", "\\")) or ".." in value.split("/"):
        raise ConfigError(f"--repo-id 不得是絕對路徑或包含 ..：{repo_id!r}")
    value = value.replace("\\", "/")
    parts = [part for part in value.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ConfigError(f"--repo-id 不合法：{repo_id!r}")
    candidate = "--".join(parts)
    if not SAFE_FILE_RE.fullmatch(candidate):
        raise ConfigError(f"--repo-id 轉換後仍含不安全字元：{candidate!r}")
    return candidate


def logical_paths(args: argparse.Namespace) -> tuple[Path, list[tuple[Path, str]]]:
    root = portable_root()
    home = Path.home()

    if args.key == "feature/config":
        canonical = root / "feature" / "config.md"
        legacy = [
            (home / ".claude" / "feature-workflow" / "config.md", "hierarchical"),
            (home / ".claude-company" / "feature-workflow" / "config.md", "hierarchical"),
            (home / ".claude-company" / "feature-workflow-config.md", "legacy_monolith"),
            (home / ".claude" / "feature-workflow-config.md", "legacy_monolith"),
        ]
        return canonical, legacy

    if args.key == "feature/project":
        if not args.repo_id:
            raise ConfigError("feature/project 需要 --repo-id")
        name = sanitize_repo_id(args.repo_id) + ".md"
        canonical = root / "feature" / "projects" / name
        legacy = [
            (home / ".claude" / "feature-workflow" / "projects" / name, "hierarchical"),
            (home / ".claude-company" / "feature-workflow" / "projects" / name, "hierarchical"),
            (home / ".claude-company" / "feature-workflow-config.md", "legacy_monolith"),
            (home / ".claude" / "feature-workflow-config.md", "legacy_monolith"),
        ]
        return canonical, legacy

    if args.key == "feature/stack":
        if not args.stack_id:
            raise ConfigError("feature/stack 需要 --stack-id")
        stack_id = safe_leaf(args.stack_id, "--stack-id")
        canonical = root / "feature" / "stacks" / f"{stack_id}.md"
        legacy = [
            (home / ".claude" / "feature-workflow" / "stacks" / f"{stack_id}.md", "hierarchical"),
            (home / ".claude-company" / "feature-workflow" / "stacks" / f"{stack_id}.md", "hierarchical"),
            (home / ".claude-company" / "feature-workflow-config.md", "legacy_monolith"),
            (home / ".claude" / "feature-workflow-config.md", "legacy_monolith"),
        ]
        return canonical, legacy

    if args.key == "bug/config":
        canonical = root / "bug" / "config.md"
        legacy = [
            (home / ".claude-company" / "bug-workflow-config.md", "hierarchical"),
            (home / ".claude" / "bug-workflow-config.md", "hierarchical"),
        ]
        return canonical, legacy

    if args.key == "bug/learning":
        if not args.project_slug:
            raise ConfigError("bug/learning 需要 --project-slug")
        slug = safe_leaf(args.project_slug, "--project-slug")
        canonical = root / "bug" / "learnings" / f"{slug}.jsonl"
        legacy = [
            (home / ".claude-company" / "bug-workflow" / "learnings" / f"{slug}.jsonl", "hierarchical"),
            (home / ".claude" / "bug-workflow" / "learnings" / f"{slug}.jsonl", "hierarchical"),
        ]
        return canonical, legacy

    raise ConfigError(f"未知 key：{args.key}")


def resolve(args: argparse.Namespace) -> dict:
    canonical, legacy = logical_paths(args)
    root = portable_root()

    if args.mode == "write":
        chosen = canonical
        source = "portable"
        representation = "hierarchical"
    elif canonical.is_file():
        chosen = canonical
        source = "portable"
        representation = "hierarchical"
    else:
        found = next(((path, rep) for path, rep in legacy if path.is_file()), None)
        if found:
            chosen, representation = found
            source = "legacy"
        else:
            chosen = canonical
            source = "missing"
            representation = "hierarchical"
    return {
        "key": args.key,
        "mode": args.mode,
        "root": str(root),
        "canonical_path": str(canonical),
        "path": str(chosen),
        "exists": chosen.is_file(),
        "source": source,
        "representation": representation,
        "legacy": source == "legacy",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve CREW portable config logical keys")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("resolve", help="resolve one logical key")
    p.add_argument("--key", choices=sorted(KEYS), required=True)
    p.add_argument("--mode", choices=["read", "write"], default="read")
    p.add_argument("--repo-id")
    p.add_argument("--stack-id")
    p.add_argument("--project-slug")
    p.add_argument("--format", choices=["json", "path"], default="json")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            result = resolve(args)
        else:
            raise ConfigError(f"未知 command：{args.command}")
    except ConfigError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    if args.format == "path":
        print(result["path"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
