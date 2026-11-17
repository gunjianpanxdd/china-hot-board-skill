#!/usr/bin/env python3
"""Annotated provider skeleton. Copy this to add a new anonymous hot-board/news source.

It depends only on the data contract (references/data-contract.md). The four dataclasses
below are the minimum shape the host service expects; a real project supplies them in its
own package. Keeping them inline here makes the template runnable standalone.

Replace every ``TODO`` and delete sections you do not need (e.g. ``search`` for a source
with no search endpoint).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from unicodedata import normalize

import httpx


# ---------------------------------------------------------------------------
# Minimal contract (mirror of references/data-contract.md)
# ---------------------------------------------------------------------------

class ProviderContractError(ValueError):
    """Response did not match the documented success contract."""


@dataclass(frozen=True)
class HeatMetrics:
    value: int | float | None
    label: str
    metric_name: str
    metrics: Mapping[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class HotItem:
    item_id: str
    platform: str
    title: str
    url: str
    rank: int | None
    heat: HeatMetrics
    summary: str
    publication_time: str | None
    collected_at: str
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ItemDetail:
    item_id: str
    content: str
    content_status: str  # full_text | summary | title_only | rejected
    publication_time: str | None
    collected_at: str
    source_url: str
    fetch_status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCapture:
    raw_text: str
    raw_suffix: str
    items: tuple[HotItem, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def number_or_none(value: object) -> int | None:
    try:
        return int(float(value))  # tolerates "1,234" after stripping commas upstream
    except (TypeError, ValueError):
        return None


def stable_id(platform: str, key: str) -> str:
    normalized = " ".join(normalize("NFKC", key).casefold().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{platform}_{digest}"


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# TODO: adapt one of the four response-family patterns
#   JSON object  -> guard code/err_no/status, read data[]
#   JSONP        -> re.match(r"var \w+=(.*);", raw) then json.loads
#   HTML embed   -> re.search(r"<!--s-data:(.*?)-->", raw) or __NEXT_DATA__
#   Search DOM   -> html.parser.HTMLParser subclass with card-boundary tracking
# ---------------------------------------------------------------------------

ROWDATA_RE = re.compile(r"var\s+\w+\s*=\s*(?P<body>.*?);?\s*$", re.DOTALL)


class MySourceProvider:
    # TODO: unique slug used as item_id prefix and platform field
    platform = "my_source"
    # TODO: weights sum to ~1.0; see references/scoring-and-ranking.md
    weights: dict[str, float] = {"hot_value": 1.0}
    # TODO: conservative fallback floors for the 25th-percentile dynamic floor
    absolute_floors: dict[str, float] = {"hot_value": 1.0}

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def collect_hot_list(self, collected_at: str) -> ProviderCapture:
        # TODO: real endpoint
        resp = self.client.get("https://example.com/hot")
        resp.raise_for_status()
        raw = resp.text
        return ProviderCapture(raw, ".json", self.parse_hot_list(raw, collected_at))

    @staticmethod
    def parse_hot_list(raw: str, collected_at: str) -> tuple[HotItem, ...]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ProviderContractError("response must be a JSON object")

        # TODO: success guard. A mismatch must raise, never return empty silently.
        if payload.get("code") not in (0, "0", 200, "200"):
            raise ProviderContractError(f"unexpected code={payload.get('code')!r}")

        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ProviderContractError("data must be a list")

        items: list[HotItem] = []
        for rank, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                continue
            # TODO: field names for this source
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            key = str(row.get("id") or title).strip()
            if not title or not key:
                continue

            # TODO: map every numeric signal into metrics with consistent keys
            metrics: dict[str, int | float] = {}
            for src, dst in (("hot", "hot_value"), ("views", "views"),
                             ("comments", "comments")):
                value = number_or_none(row.get(src))
                if value is not None:
                    metrics[dst] = value

            primary = metrics.get("hot_value")
            items.append(HotItem(
                item_id=stable_id(MySourceProvider.platform, key),
                platform=MySourceProvider.platform,
                title=title,
                url=url or f"https://example.com/item/{key}",
                rank=rank,
                heat=HeatMetrics(primary, str(primary or ""), "hot_value", metrics),
                summary=str(row.get("summary") or title),
                publication_time=None,  # TODO: normalize to UTC ISO-8601 if available
                collected_at=collected_at,
                raw_payload={k: v for k, v in row.items() if v not in (None, "")},
            ))
        if not items:
            raise ProviderContractError("board contained no valid items")
        return tuple(items)

    def fetch_detail(self, item: HotItem, collected_at: str) -> ItemDetail:
        # TODO: body extraction chain: container selector -> structured JSON -> GNE -> reject
        # TODO: clean site chrome via a module-level _NOISE / _TAIL_MARKERS constant
        try:
            html = self.client.get(item.url).text
        except httpx.HTTPError:
            html = ""

        content = html  # TODO: replace with real extraction + validate_full_text
        status = "full_text" if content else "rejected"
        return ItemDetail(
            item.item_id,
            content,
            status,
            item.publication_time,
            collected_at,
            item.url,
            "success" if content else "rejected:empty",
        )

    def search(self, keyword: str, *, page: int = 1, page_size: int = 20,
               collected_at: str | None = None) -> ProviderCapture:
        # TODO: delete if the source has no search endpoint
        raise NotImplementedError

    def enrich_metrics(self, items: Sequence[HotItem],
                       collected_at: str) -> tuple[HotItem, ...]:
        # TODO: optional second-call metric enrichment (e.g. comment counts)
        return tuple(items)

    def close(self) -> None:
        # TODO: close any browser renderer / extra resources held by the provider
        pass
