# Authoring playbook

Step-by-step procedures for the two jobs this skill exists for: adding a provider, and
diagnosing a broken one.

## Add a provider

### 1. Probe before writing code

Save a real response to a fixture file. Confirm:

- The endpoint works anonymously (no cookie, no token). If it needs auth, this skill does
  not cover it — stop and flag the source.
- Which response family it is: JSON object, JSONP assignment, HTML with embedded JSON, or
  a search results DOM. Pick the matching pattern from `platform-catalog.md`.
- Where the row list lives and what the success guard is (`code`, `err_no`, `status`).

### 2. Implement the interface

```python
class MyProvider:
    platform = "my_source"
    weights = {"hot_value": 1.0}
    absolute_floors = {"hot_value": 1.0}

    def __init__(self, client): ...
    def collect_hot_list(self, collected_at: str) -> ProviderCapture: ...
    def fetch_detail(self, item: HotItem, collected_at: str) -> ItemDetail: ...
    def search(self, keyword, *, page=1, page_size=20, collected_at=None) -> ProviderCapture: ...   # optional
    def enrich_metrics(self, items, collected_at) -> tuple[HotItem, ...]: ...                        # optional
```

Keep this surface identical. Runtime wiring (which providers run, when, and where results
go) lives in the host service, not here.

### 3. Parse defensively

- Guard the envelope **before** reading rows. Raise `ProviderContractError` on mismatch.
- Accept 2–3 plausible row locations if the site has a history of moving them (The Paper's
  `_ROW_PATHS` is the model).
- Skip bad rows individually; never let one malformed row kill the whole board.
- Use `number_or_none(value)` for every numeric field — strings with commas and floats must
  not crash parsing.
- Normalize timestamps to UTC ISO-8601. Locale naive datetimes get the platform timezone.

### 4. Normalize rows

- Stable `item_id`: native id if available, else sha256 of a normalized key (NFKC,
  casefold, collapse whitespace), truncated to 16 hex chars, prefixed with platform slug.
- Preserve every original field in `raw_payload` (drop only `None`/empty).
- Put all numbers into `heat.metrics` with consistent keys (`views`, `comments`, `click`,
  `votes`, `interactions`, …), and pick one `metric_name` / `value` as primary.

### 5. Extract the body with a fallback chain

Order: native container selector → structured JSON (`__NEXT_DATA__`, JSON-LD `articleBody`,
`__INITIAL_STATE__`) → `GeneralNewsExtractor` → reject.

- Put site chrome in module-level constants (`_NOISE_EXACT`, `_TAIL_MARKERS`), not scattered
  inline regex.
- Run `validate_full_text` and honor its `reasons` when tuning.
- For JS-heavy detail pages, prefer a bounded shared browser renderer; swallow renderer
  failures into a typed "unavailable" error with no sensitive context.

### 6. Degrade, don't crash

- Unknown envelope / code → empty `ProviderCapture` with `metadata["schema_warning"]`.
- HTTP failure → return an item with `content_status="summary"`/`title_only` and a
  `fetch_status` diagnostic; keep the item.
- Captcha / anti-bot signature → empty capture; never attempt bypass.
- One platform's failure must never abort the others.

### 7. Declare heat rules

Fill `weights` (≈1.0 total) and `absolute_floors` (conservative). See
`scoring-and-ranking.md`.

### 8. Verify

```
python scripts/verify_provider.py --fixture saved_response.json --platform my_source
```

Check: non-empty items, stable IDs across two runs, metrics populated, and a reasonable
`full_text` rate on a few real detail URLs.

## Diagnose a failure

| Symptom | Likely cause | First checks |
|---|---|---|
| Empty items, no exception | Row path / envelope changed | Dump `raw_text`; compare to documented shape; check `code`/`err_no`/`status` guard; try alternate row paths |
| `ProviderContractError` on every run | Success guard inverted or endpoint returns an error page | Inspect HTTP status and first 500 chars of body |
| Many `rejected` details | Body selector too narrow, or chrome grew | Read `ContentValidation.reasons`; widen selectors; add new noise strings |
| `partial` status | Expected degradation | Read `metadata["schema_warning"]`, not a stack trace |
| Duplicated / unstable `item_id` | Non-stable ID source | Switch to native id or normalized sha256 key |
| Heat all zero | Metrics not mapped, or values are strings | Check `number_or_none` applied; check `heat.metrics` keys |
| Search returns wrong/empty results | Pagination ignored or markup changed | Check single-page constraints (Juejin 20-item cap); re-derive card boundaries; avoid recommendation fallbacks |

## Anti-patterns

- Silently returning the first list found in a payload — validate the envelope first.
- Hard-coding one row path when the site has moved it before.
- Treating search recommendations as results when the result list is empty.
- Letting a renderer/HTTP exception escape with credentials or full URLs in the message.
- Ranking on raw heat magnitude instead of weighted percentiles.
- Putting runtime concerns (locks, timers, DB writes) in a provider.
