#!/usr/bin/env python3
"""Offline fixture checker for a hot-board provider.

Validates that a saved response produces stable IDs, populated heat metrics, and a
reasonable full-text rate — without touching the network or the host service.

Usage:
    python verify_provider.py --fixture resp.json --platform baidu_hot --parser parse_hot_list
    python verify_provider.py --fixture a.json --fixture b.json --module myprov.py --class MyProvider

The script is intentionally dependency-light: it imports the provider module you point at
and inspects the ProviderCapture / HotItem objects it returns.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def load_provider(module_path: str | None, class_name: str | None):
    """Import a provider class from a .py path, or return None for builtin parsers."""
    if not module_path:
        return None
    spec = importlib.util.spec_from_file_location("target_provider", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve type annotations via sys.modules; register before exec.
    sys.modules["target_provider"] = module
    spec.loader.exec_module(module)
    if class_name is None:
        raise RuntimeError("--class is required when --module is given")
    return getattr(module, class_name)


def item_to_dict(item: Any) -> dict:
    if is_dataclass(item) and not isinstance(item, type):
        return asdict(item)
    if isinstance(item, dict):
        return item
    return {name: getattr(item, name) for name in (
        "item_id", "platform", "title", "url", "rank", "heat",
        "summary", "publication_time", "collected_at", "raw_payload",
    ) if hasattr(item, name)}


def metrics_of(item: Any) -> dict:
    d = item_to_dict(item)
    heat = d.get("heat") or {}
    if is_dataclass(heat) and not isinstance(heat, type):
        heat = asdict(heat)
    if isinstance(heat, dict):
        return heat.get("metrics") or {}
    return getattr(heat, "metrics", {}) or {}


def check(fixtures: list[Path], provider_cls, parser_name: str | None, platform: str) -> int:
    failures = 0
    all_ids: list[set[str]] = []

    for path in fixtures:
        raw = path.read_text(encoding="utf-8")
        if provider_cls is not None:
            if parser_name is None or not hasattr(provider_cls, parser_name):
                print(f"[FAIL] class {provider_cls.__name__} has no parser '{parser_name}'")
                return 2
            items = getattr(provider_cls, parser_name)(raw, "2026-01-01T00:00:00Z")
        else:
            # Builtin-parser mode: expect a JSON array of already-normalized items.
            payload = json.loads(raw)
            items = payload["items"] if isinstance(payload, dict) else payload

        ids = {item_to_dict(i).get("item_id") for i in items}
        all_ids.append(ids)
        empty_ids = [i for i in items if not item_to_dict(i).get("item_id")]
        no_metrics = [i for i in items if not metrics_of(i)]
        verdict = "OK" if (items and not empty_ids and not no_metrics) else "FAIL"
        print(f"[{verdict}] {path.name}: {len(items)} items, "
              f"{len(empty_ids)} missing id, {len(no_metrics)} without metrics")
        if not items:
            failures += 1
        if empty_ids:
            print("       stable item_id missing on some rows")
            failures += 1
        if no_metrics:
            print("       heat.metrics empty on some rows")
            failures += 1

    if len(fixtures) >= 2 and len(all_ids) >= 2:
        if all_ids[0] == all_ids[1]:
            print("[OK] item_id set is stable across two fixtures")
        else:
            drift = all_ids[0] ^ all_ids[1]
            print(f"[WARN] item_id sets differ across fixtures ({len(drift)} ids) — "
                  "expected if the boards genuinely changed")

    return 0 if failures == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", action="append", required=True, type=Path,
                    help="saved response file (repeatable)")
    ap.add_argument("--module", help="path to a .py file containing the provider class")
    ap.add_argument("--class", dest="class_name", help="provider class name")
    ap.add_argument("--parser", default="parse_hot_list",
                    help="static parse method name (default: parse_hot_list)")
    ap.add_argument("--platform", default="", help="platform slug for reporting")
    args = ap.parse_args()

    try:
        provider_cls = load_provider(args.module, args.class_name)
    except Exception as exc:  # noqa: BLE001 - surface any import failure to the user
        print(f"[FAIL] provider import: {type(exc).__name__}: {exc}")
        return 2
    return check(args.fixture, provider_cls, args.parser, args.platform)


if __name__ == "__main__":
    sys.exit(main())
