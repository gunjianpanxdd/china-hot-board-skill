---
name: china-hot-board-skill
description: Collect, parse and normalize trending hot boards and news from Chinese platforms (Toutiao, Baidu, Sina News, NetEase, The Paper, Juejin) into one strict, heat-scored contract. This skill should be used when adding a new hot-board/news source, writing a schema-resilient HTML/JSON/JSONP parser, cleaning article body text out of page chrome, defining heat thresholds and ranking rules, or diagnosing a failed or partial platform fetch. Keywords: Chinese hot board scraper, 中文热榜采集, 新闻聚合, trending news aggregator, content idea radar. All bundled endpoints are anonymous; no login cookies required.
agent_created: true
---

# China Hot Board Skill

Collect China's public hot boards and news, turn six messy heterogeneous sources into
one strict, heat-scored `HotItem` contract, and stay alive when a site restructures its
HTML or JSON.

## Overview

This skill captures the engineering playbook behind a production multi-platform hot-board
collector: endpoint discovery, schema-resilient parsing, article-body extraction, heat
qualification, and graceful degradation. It does **not** run a scheduler, hold cookies, or
write to a database — those stay in the host service. The unit of reuse is *how to add and
maintain a provider*, not the runtime itself.

## When to use

Use this skill when a task involves any of:

- Adding a new Chinese hot-board / news source to an existing collector.
- Writing or fixing a parser for a JSON, JSONP, HTML-embedded (`<!--s-data-->`,
  `__NEXT_DATA__`, `__INITIAL_STATE__`) or search-DOM response.
- Extracting clean article text from a page full of navigation and footer noise.
- Designing heat metrics, absolute floors, dynamic percentiles, or ranking rules.
- Diagnosing why one platform returned `partial` / empty while others succeeded.

## Workflow decision tree

| Goal | Path |
|---|---|
| Add a brand-new platform | Read `references/platform-catalog.md` → follow "Add a provider" in `references/authoring-playbook.md` → verify with `scripts/verify_provider.py` |
| An existing platform broke | See "Diagnose a failure" in `references/authoring-playbook.md` |
| Need the data contract / field meanings | `references/data-contract.md` |
| Need heat scoring & thresholds | `references/scoring-and-ranking.md` |
| Reuse a parser skeleton | `scripts/provider_template.py` |

## The normalized contract (non-negotiable)

Every provider returns `ProviderCapture(raw_text, raw_suffix, items, metadata)` where each
item is a frozen `HotItem`: `item_id, platform, title, url, rank, heat(HeatMetrics),
summary, publication_time, collected_at, raw_payload`.

Three invariants separate this from a naive scraper:

1. **Strict success contract.** A response that does not match the expected envelope
   raises `ProviderContractError` — never silently return garbage rows. Exception: a
   recognized schema drift may downgrade to `partial` with a `schema_warning` in metadata
   (see `thepaper.py` `_parse_rows` → empty rows on unknown `code`).
2. **Evidence-backed heat.** `HeatEvidence` must carry a positive signal — either
   `official_hot_board` with `platform_rank > 0` or `native_hot_value > 0`, or a named
   public-engagement metric above its floor. See `references/data-contract.md`.
3. **Full-text validation.** Article bodies pass `validate_full_text`: min characters
   (80 native / 200 for GNE fallback), ≥2 paragraphs or ≥3 sentences, and page-chrome
   hit count < 4. Otherwise `content_status` is `rejected` / `summary` / `title_only`.

## Add a provider — the 8 moves

1. **Probe the endpoint anonymously.** Confirm it needs no cookie; if it does, stop —
   this skill is for anonymous sources. Record the exact URL and response shape.
2. **Pick the response family:** JSON dict → `err_no`/`code` guard + `data[]`; JSONP →
   `var data=...` regex then `json.loads`; HTML-embedded → regex the JSON comment/script;
   search DOM → `HTMLParser` subclass with card-boundary tracking.
3. **Copy the matching skeleton** from `scripts/provider_template.py`; keep the class
   interface: `collect_hot_list`, `fetch_detail`, optional `search` / `enrich_metrics`,
   plus `platform`, `weights`, `absolute_floors`.
4. **Normalize every row into `HotItem`.** Stable `item_id` = `<platform>_<hash or id>`;
   put all platform-specific fields in `raw_payload`; map every numeric signal into
   `heat.metrics`.
5. **Write body extraction in a fallback chain:** native container selector →
   JSON-LD / `__NEXT_DATA__` → `GeneralNewsExtractor` → reject. Put site-specific chrome
   strings in a `_NOISE_*` constant, not inline regex soup.
6. **Handle drift as degradation, not crash.** Unknown envelope → empty capture with
   `metadata["schema_warning"]`; HTTP failure → `partial` status, never `failed` for the
   whole run. One bad platform must not abort the others.
7. **Define heat rules:** `weights` for percentile scoring, `absolute_floors` as the
   fallback for the 25th-percentile dynamic floor. See `references/scoring-and-ranking.md`.
8. **Verify:** run `python scripts/verify_provider.py --fixture <saved_response>` and
   check stable IDs, non-empty metrics, and `full_text` rate on a few real articles.

## Diagnose a failure

- **Empty items** → response shape drifted; dump `raw_text` and diff against the
  documented shape. Check the `s-data` / JSONP / `code` guard first.
- **Too many `rejected` details** → body selector is too narrow or chrome noise rose;
  widen selectors, add the new noise string, verify `validate_full_text` reasons.
- **`partial` status** → expected degradation; read `metadata["schema_warning"]`, not a
  stack trace.
- **Captcha / anti-bot** → the source is drifting toward gated access. Do not attempt to
  bypass; downgrade to empty/`partial` and flag the platform for a compliance review.

## Scope boundary

Do skill-ify: endpoint knowledge, parser skeletons, noise dictionaries, data contract,
heat rules, degradation playbook, verification.
Do **not** skill-ify: Redis locks/switches, APScheduler timing, DB upsert, cookie pools —
these are runtime concerns of the host service and are intentionally out of scope.

## Resources

### scripts/
- `provider_template.py` — annotated skeleton implementing the full provider interface.
- `verify_provider.py` — offline fixture-based checker (stable IDs, metrics, full-text rate).

### references/
- `platform-catalog.md` — the six platforms: endpoints, response families, heat metrics.
- `data-contract.md` — `HotItem` / `HeatMetrics` / `HeatEvidence` / validation semantics.
- `scoring-and-ranking.md` — weights, absolute floors, dynamic percentiles, sort order.
- `authoring-playbook.md` — detailed "add a provider" and "diagnose a failure" procedures.
