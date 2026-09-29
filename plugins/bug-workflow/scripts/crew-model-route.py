#!/usr/bin/env python3
"""CREW deterministic model profile router.

The router chooses a provider-neutral profile (NONE/FAST/STANDARD/DEEP).
Host adapters may then map that profile to a concrete model/reasoning level.
It never claims a Host actually applied the mapping; that remains the adapter's job.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = PLUGIN_ROOT / "references" / "model-routing.json"


class RoutingError(Exception):
    pass


def load_policy() -> dict:
    try:
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoutingError(f"找不到 model routing policy：{POLICY_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RoutingError(f"model-routing.json 無法解析：{exc}") from exc
    validate_policy(data)
    return data


def validate_policy(data: dict) -> None:
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise RoutingError("profiles 必須是 JSON object")
    required = {"NONE", "FAST", "STANDARD", "DEEP"}
    if set(profiles) != required:
        raise RoutingError(f"profiles 必須剛好是 {sorted(required)}")
    ranks = {name: profiles[name].get("rank") for name in required}
    if ranks != {"NONE": 0, "FAST": 1, "STANDARD": 2, "DEEP": 3}:
        raise RoutingError(f"profile rank 不合法：{ranks}")

    for task, profile in data.get("task_defaults", {}).items():
        if profile not in required:
            raise RoutingError(f"task_defaults.{task} 指向未知 profile：{profile}")

    for dimension in ("risk", "complexity"):
        for key, profile in data.get("minimum_profile", {}).get(dimension, {}).items():
            if profile not in required:
                raise RoutingError(f"minimum_profile.{dimension}.{key} 指向未知 profile：{profile}")

    for host, mapping in data.get("host_mappings", {}).items():
        missing = required - set(mapping)
        if missing:
            raise RoutingError(f"host_mappings.{host} 缺少：{sorted(missing)}")


def max_profile(policy: dict, *profiles: str) -> str:
    ranks = {name: item["rank"] for name, item in policy["profiles"].items()}
    return max(profiles, key=lambda p: ranks[p])


def escalate(policy: dict, profile: str, failures: int) -> tuple[str, list[str]]:
    cfg = policy.get("failure_escalation", {})
    threshold = int(cfg.get("after_failures", 0))
    levels = int(cfg.get("levels", 0))
    if threshold <= 0 or levels <= 0 or failures < threshold or profile in ("NONE", "DEEP"):
        return profile, []

    ordered = ["NONE", "FAST", "STANDARD", "DEEP"]
    idx = ordered.index(profile)
    target = ordered[min(len(ordered) - 1, idx + levels)]
    return target, [f"failures={failures} >= {threshold}: {profile}->{target}"]


def route(
    policy: dict,
    task: str,
    risk: str,
    complexity: str,
    sensitive: list[str],
    failures: int,
    host: str,
) -> dict:
    reasons: list[str] = []
    base = policy.get("task_defaults", {}).get(task, "STANDARD")
    profile = base
    reasons.append(f"task:{task}->{base}")

    minimum = policy.get("minimum_profile", {})
    risk_min = minimum.get("risk", {}).get(risk, "NONE")
    if risk_min != "NONE":
        reasons.append(f"risk:{risk}>={risk_min}")
    profile = max_profile(policy, profile, risk_min)

    complexity_min = minimum.get("complexity", {}).get(complexity, "NONE")
    if complexity_min != "NONE":
        reasons.append(f"complexity:{complexity}>={complexity_min}")
    profile = max_profile(policy, profile, complexity_min)

    deep_tags = set(policy.get("deep_sensitive_tags", []))
    matched = sorted(deep_tags.intersection(sensitive))
    if matched:
        profile = "DEEP"
        reasons.append("sensitive:" + ",".join(matched) + "->DEEP")

    profile, escalation_reasons = escalate(policy, profile, failures)
    reasons.extend(escalation_reasons)

    host_mapping = policy.get("host_mappings", {}).get(host)
    if host_mapping is None:
        raise RoutingError(
            f"未知 host={host!r}；可用：{', '.join(sorted(policy.get('host_mappings', {})))}"
        )

    return {
        "task": task,
        "base_profile": base,
        "profile": profile,
        "risk": risk,
        "complexity": complexity,
        "sensitive": sensitive,
        "failures": failures,
        "reasons": reasons,
        "host": host,
        "host_mapping": host_mapping.get(profile, {}),
        "adapter_must_confirm_application": profile != "NONE",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crew-model-route.py")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="驗證 model-routing.json")

    p = sub.add_parser("route", help="計算 model profile")
    p.add_argument("--task", required=True)
    p.add_argument("--risk", choices=["low", "medium", "high"], default="low")
    p.add_argument("--complexity", choices=["low", "medium", "high"], default="low")
    p.add_argument("--sensitive", default="", help="逗號分隔，例如 security,transaction")
    p.add_argument("--failures", type=int, default=0)
    p.add_argument("--host", default="portable")
    p.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        policy = load_policy()
        if args.command == "validate":
            print(f"✅ model-routing.json 驗證通過（schema_version={policy.get('schema_version')}）")
            return 0

        sensitive = sorted({x.strip() for x in args.sensitive.split(",") if x.strip()})
        result = route(
            policy=policy,
            task=args.task,
            risk=args.risk,
            complexity=args.complexity,
            sensitive=sensitive,
            failures=max(0, args.failures),
            host=args.host,
        )
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            mapping = result["host_mapping"]
            print(
                f"{result['profile']} | task={result['task']} | host={result['host']} | "
                f"mapping={json.dumps(mapping, ensure_ascii=False)}"
            )
            for reason in result["reasons"]:
                print(f"- {reason}")
        return 0
    except RoutingError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
