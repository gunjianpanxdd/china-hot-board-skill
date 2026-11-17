# Data contract

The frozen dataclasses that every provider produces and downstream consumers rely on.
These are immutable by design: normalization happens at the boundary, never mid-pipeline.
This document describes the contract; a provider never redefines it.

## ProviderCapture

```
ProviderCapture(raw_text: str, raw_suffix: str,
                items: tuple[HotItem, ...],
                metadata: Mapping[str, str] = {})
```

- `raw_text` — the exact response body, kept for diagnosis when schema drifts.
- `raw_suffix` — file extension hint (`.json`, `.html`, `.txt`) for raw dumps.
- `items` — normalized items; empty tuple is a valid degradation result.
- `metadata` — non-secret diagnostic strings, e.g. `{"schema_warning": "thepaper envelope code=501"}`.

## HotItem

| Field | Type | Meaning |
|---|---|---|
| `item_id` | str | Stable across runs: `<platform>_<hash or native id>`. sha256 of NFKC/casefolded query is acceptable. |
| `platform` | str | Provider's `platform` slug, e.g. `baidu_hot`. |
| `title` | str | Cleaned headline. |
| `url` | str | Canonical article URL (fall back to a stable board URL). |
| `rank` | int \| None | Board rank starting at 1; `None` for search results with no rank. |
| `heat` | HeatMetrics | Primary heat value + all metrics. |
| `summary` | str | Description / abstract / source; never page chrome. |
| `publication_time` | str \| None | Normalized to UTC ISO-8601 (`...Z`). |
| `collected_at` | str | UTC ISO-8601 collection instant. |
| `raw_payload` | Mapping | All platform-specific fields preserved for evidence & reprocessing. |

## HeatMetrics

```
HeatMetrics(value: int | float | None, label: str,
            metric_name: str, metrics: Mapping[str, int|float] = {})
```

- `value` — the single primary number (or `None` when absent).
- `metric_name` — which metric is primary (`hot_score`, `hot_value`, `top_num`, `hot_rank`, `engagement`, `search_rank`, `public_engagement`).
- `metrics` — every numeric signal from the row, keyed consistently (`views`, `comments`,
  `click`, `votes`, `interactions`, `praise_times`, …). Downstream ranking reads these keys.

Rule: **do not drop secondary metrics** just because one is primary. The scoring layer needs
the whole vector to compute weighted percentiles.

## HeatEvidence

A frozen, self-validating record. `__post_init__` rejects weak evidence:

- `source_kind == "official_hot_board"` requires:
  - `"official_hot_board"` present in `qualified_by`, **and**
  - a positive signal: `platform_rank > 0` **or** `native_hot_value > 0`.
- `source_kind == "public_engagement"` requires at least one metric named in `qualified_by`
  whose value is `> 0`.

```
HeatEvidence(source_kind, platform_rank, native_hot_value,
             metrics={}, threshold_metrics={}, qualified_by=())
```

`threshold_metrics` carries the floors actually applied (for audit). `qualified_by` names
which metrics cleared their floor.

## ItemDetail

```
ItemDetail(item_id, content, content_status, publication_time,
           collected_at, source_url, fetch_status, metadata={})
```

`content_status` is one of `full_text | summary | title_only | rejected`.
`fetch_status` records how it was obtained (`success`, `partial:<diagnostic>`,
`rejected:<reason>`). A failing detail fetch must not discard the `HotItem`.

## ContentValidation

Produced by `validate_full_text(content, title, summary, parser=...)`:

- `status`: `accepted` | `rejected`.
- `reasons`: `title_or_summary` (body is just the headline repeated), `too_short`,
  `insufficient_structure`, `page_chrome`.
- Thresholds: `MIN_NATIVE_ARTICLE_CHARACTERS = 80`,
  `MIN_FALLBACK_ARTICLE_CHARACTERS = 200` (for `parser == "gne"`).
- Structure: at least 2 paragraphs **or** 3 sentence-ending marks (`。！？!?`).
- Chrome: fewer than 4 hits of navigation/footer strings (登录, 发表评论, 版权所有,
  特别声明, 阅读排行榜, …).

A `QualifiedArticle` requires `content_status == "full_text"`, validation `accepted`, and
non-empty `heat_evidence.qualified_by` — enforced in `__post_init__`.

## Provider error taxonomy

| Exception | Meaning | Handling |
|---|---|---|
| `ProviderContractError(ValueError)` | Response does not match success contract | Treat as data error; log, degrade platform to `partial` or empty |
| `MissingCredentialError` | Required env credential absent | Configure credential; not used by anonymous providers |
| `AuthenticationExpiredError` | Credential expired | Refresh credential |
| `AuthenticationBlockedError` | Credential blocked | Stop; compliance review |

`ProviderContractError` is the normal "site changed" signal. Never let it bubble up as an
uncaught exception that aborts a whole multi-platform run.
