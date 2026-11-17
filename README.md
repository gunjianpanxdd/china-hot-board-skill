# China Hot Board Skill

> English · [中文文档](README.zh-CN.md)
>
> A production-grade agent skill for collecting and normalizing trending hot boards and news from Chinese platforms — Toutiao, Baidu, Sina News, NetEase, The Paper, and Juejin.

[![Skill](https://img.shields.io/badge/type-agent%20skill-blueviolet)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-6%20sources-orange)](#supported-platforms)

Collect China's public hot boards and turn six messy, heterogeneous sources into one strict,
heat-scored `HotItem` contract. This is the engineering playbook — endpoint knowledge,
schema-resilient parsers, article-body extraction, heat qualification, and graceful
degradation — distilled from a production multi-platform collector.

**It is knowledge, not a running service.** No scheduler, no cookies, no database. The unit
of reuse is *how to add and maintain a data source*, so any agent can extend a collector
without re-discovering every site's quirks.

## Why another hot-board scraper?

Most scrapers give you raw rows and break the moment a site changes its markup. This skill
packages the things that actually cost engineering time:

- **Strict success contract** — malformed responses raise instead of leaking garbage rows.
- **Schema-drift degradation** — a changed envelope downgrades one source to `partial`
  (with a `schema_warning`) instead of crashing the whole collection run.
- **Evidence-backed heat** — every item carries a positive heat signal; no silent zeros.
- **Full-text validation** — article bodies are checked for length, structure, and page
  chrome, so downstream content work never starts from navigation noise.
- **Anonymous endpoints only** — every bundled source works without login cookies.

## Supported platforms

| Platform | Endpoint type | Heat signal |
|---|---|---|
| Toutiao 今日头条 | JSON hot-board API | `HotValue` |
| Baidu 百度热搜 | HTML `<!--s-data-->` | `hotScore` |
| Sina News 新浪新闻 | JSONP `GetTopDataList.php` | `top_num` + comment count |
| NetEase 网易新闻 | JSON hot-list API | hot/click/comment/vote mix |
| The Paper 澎湃新闻 | JSON (`cache.thepaper.cn`) | interaction + praise |
| Juejin 掘金 | JSON rank API | `hot_rank` + engagement |

## Install

Copy the folder into your agent's skills directory (e.g. `.claude/skills/`,
`.workbuddy/skills/`, or your platform's equivalent). The agent loads `SKILL.md` on demand.

```bash
git clone https://github.com/gunjianpanxdd/china-hot-board-skill.git
cp -r china-hot-board-skill <your-project>/.claude/skills/
```

## Usage

Just ask your agent in natural language — the `description` in `SKILL.md` triggers it:

- "Add a new hot-board source for Zhihu."
- "The Baidu collector returned empty items, diagnose it."
- "Write a parser for this JSONP hot list."
- "How should I set heat thresholds for a new platform?"

Or invoke it explicitly: `/china-hot-board-skill`

## What's inside

```
china-hot-board-skill/
├── SKILL.md                     # triggers, workflow, non-negotiable contract
├── scripts/
│   ├── provider_template.py     # annotated provider skeleton
│   └── verify_provider.py       # offline fixture checker
└── references/
    ├── platform-catalog.md      # 6 platforms: endpoints, response families, metrics
    ├── data-contract.md         # HotItem / HeatMetrics / HeatEvidence / validation
    ├── scoring-and-ranking.md   # weights, floors, dynamic percentiles, sort order
    └── authoring-playbook.md    # add-a-provider & diagnose-a-failure procedures
```

## The contract at a glance

Every provider returns `ProviderCapture(raw_text, raw_suffix, items, metadata)`, where each
item is a frozen `HotItem`:

```
item_id · platform · title · url · rank · heat(HeatMetrics)
· summary · publication_time · collected_at · raw_payload
```

Three invariants: **strict success contract**, **evidence-backed heat**, **full-text
validation**. See [references/data-contract.md](references/data-contract.md).

## Scope

**In scope:** endpoint knowledge, parser skeletons, noise dictionaries, data contract, heat
rules, degradation playbook, verification scripts.

**Out of scope:** schedulers, Redis locks/switches, DB upsert, cookie pools — runtime
concerns that stay in the host service.

## License

MIT — see [LICENSE](LICENSE).

> The bundled platforms are public endpoints. Respect each site's terms of use and robots
> policy; this skill is for assembling and normalizing publicly available trend data.
