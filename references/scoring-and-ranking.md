# Scoring and ranking

How raw platform metrics become a comparable heat score and a stable ordering. All functions
are pure; re-running on the same inputs yields the same result.

## Two layers of heat

1. **Qualification** — does an item clear the bar at all? Uses `HeatEvidence` + floors
   (`data-contract.md`). An item whose evidence fails validation cannot be a
   `QualifiedArticle`.
2. **Ranking** — among qualified articles, how do we order them? Uses weighted percentile
   scoring, then a stable multi-key sort.

## Dynamic floors

```
dynamic_floors(board_metrics, absolute_floors) -> Dict[metric, floor]
```

- For each metric in `absolute_floors`, compute the **25th percentile** of all positive
  values on the board (`positive_percentile(values, 0.25)`, linear interpolation).
- If there are no positive values, fall back to the platform's `absolute_floors[metric]`.
- Rationale: a floor that adapts to today's board avoids a fixed threshold that is trivially
  cleared on a slow news day or impossible on a hot one.

```
qualifies_public_metrics(metrics, floors) -> tuple[metric, ...]
```

Returns the metrics where `metrics[m] >= floors[m]`. Feed this tuple into
`HeatEvidence.qualified_by` for `public_engagement` sources.

## Declared weights / floors per platform

| Platform | weights | absolute_floors |
|---|---|---|
| Sina News | `top_num 0.70`, `comments 0.30` | `comments 10.0` |
| NetEase | `hot_value 0.40`, `click 0.30`, `comments 0.15`, `votes 0.10`, `thread_votes 0.05` | `comments 10.0` |
| The Paper | `interaction_num 0.60`, `praise_times 0.40` | `interaction_num 1.0`, `praise_times 10.0` |
| Baidu | `hot_score 1.0` | `hot_score 1.0` |
| Toutiao | (primary `hot_value`; search uses engagement) | — |
| Juejin | (primary `hot_rank`; engagement metrics available) | — |

A new platform should declare `weights` summing to ~1.0 and conservative absolute floors.

## Percentile scoring

```
rank_platform_articles(articles, weights) -> tuple[QualifiedArticle, ...]
```

For each metric in `weights`, transform every article's value with `log1p(max(0, v))`, then map
to a percentile in `[0, 1]` by rank among distinct values (all-zero → all 0.0; single distinct
positive → 1.0). `platform_heat_score = Σ weight[m] × percentile[m]`.

Using log + rank-percentile (not raw magnitude) prevents one viral outlier from flattening
every other score and makes scores comparable across days.

## Sort order (stable multi-key, applied in this exact sequence)

Python's sort is stable, so keys are applied from least to most significant:

1. `platform_heat_score` descending (most significant — applied last)
2. count of positive evidence metrics descending
3. `source_kind != "official_hot_board"` (official boards first)
4. `platform_rank` ascending (`None` → `10**9`)
5. `publication_time` descending (`None` → empty string)
6. `item_id` ascending (final tiebreak for determinism)

Implementation applies them in reverse order (6 → 1) so the last `.sort()` is the primary key.
Preserve this if rewriting — changing the sequence silently changes output ordering.

## Practical guidance

- Never rank on `rank` alone; board position is one signal, not the score.
- Keep `threshold_metrics` on the evidence so a reviewer can see which floors were applied
  on the day.
- If a platform has only one metric, still populate `metrics` with secondary signals — they
  feed the "positive evidence count" sort key and future weight expansion.
- Search results without a native rank use `search_rank` derived from position; treat their
  heat as relative, not absolute.
