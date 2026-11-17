# Platform catalog

Six anonymous Chinese hot-board / news sources, with the exact endpoint, response family,
parser strategy, and heat signals observed in production. Use this when adding a source or
diagnosing one that went empty.

All values are read from the live providers. `weights` / `absolute_floors` are the platform's
declared contribution to ranking (see `scoring-and-ranking.md`).

## Toutiao 今日头条

- **Hot board:** `GET https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc`
- **Search:** `GET https://so.toutiao.com/search/` with `keyword, pd=information,
  format=json, count=10, offset=0`
- **Response family:** JSON object. Hot board rows in `data[]`; guard `status == "success"`.
  Search accepts two shapes — `dom` (HTML string) or legacy `data[]`.
- **Row fields:** `ClusterIdStr`/`ClusterId`, `Title`, `Url`, `HotValue`, `QueryWord`.
- **Heat metrics:** `hot_value` (board); `reads` + `comments` summed into `engagement`, or
  `search_rank` fallback for search.
- **Detail:** article page via `article_text`; falls back to a shared lazy Playwright
  renderer when the plain fetch is too short (<120 chars / <2 lines / <100 substantive
  chars). Renderer is bounded (semaphore, shared thread + event loop) and its exceptions
  are swallowed into `ToutiaoRendererUnavailable` with no sensitive context.
- **Noise control:** `_clean_rendered_article_text` drops nav lines and `_is_page_chrome_line`
  detects high-coverage UI chrome; trending detail keeps only blocks titled
  事件详情 / 事件脉络 / 相关内容.

## Baidu 百度热搜

- **Hot board:** `GET https://top.baidu.com/board?tab=realtime`
- **Search:** `GET https://www.baidu.com/s?wd=<query>` (used for discovery, not the primary
  `search()` which returns empty)
- **Response family:** HTML with `<!--s-data:{...}-->` comment (`_S_DATA` regex), parsed as
  JSON. Row list lives at `data.cards[].content[]` (new) or `cards[].content[]` (old), with
  one extra unwrap when `content[0].content` is a list.
- **Row fields:** `word`/`title`, `query`, `hotScore`/`hotTag`, `desc`, `rawUrl`/`url`.
- **Heat metrics:** `hot_score`.
- **Detail:** resolve `rawUrl` through up to 5 redirect hops; reject internal Baidu surfaces
  (`passport.`, `wappass`, `/s`, `/link`, `v.baidu.com`, `tieba`, `haokan`, `image`).
  Body extraction chain: JSON-LD `articleBody` → `article` tag → `GeneralNewsExtractor`.
- **Captcha:** `_looks_like_captcha` detects 百度安全验证 / wappass / verify+captcha → empty
  capture (do not bypass).
- **Relevance:** `_event_relevant` matches a parent event to a candidate article using CJK
  bigram overlap (≥2 bigrams and ≥25% of the smaller set), ASCII alnum tokens, or short
  exact substrings.

## Sina News 新浪新闻

- **Hot board:** `GET https://top.news.sina.com.cn/ws/GetTopDataList.php?...top_show_num=50...`
- **Search:** `GET https://search.sina.com.cn/api/news?q=<kw>&page=<n>`
- **Comments:** `GET https://comment5.news.sina.com.cn/page/info?channel=<c>&newsid=<id>`
- **Response family:** JSONP assignment `var data = {...};` (`_JSONP` regex) for hot list;
  JSON for search with rows under `result.data` / `data.list|data|items`.
- **Row fields:** `title`, `url`, `top_num`, `create_date`, `media`, `commentid`.
- **Heat metrics:** `top_num` (weight 0.70) + `comments` (weight 0.30, absolute floor 10).
- **Detail selectors:** `#artibody`, `#article-content`, `.article-content`,
  `.article-content-left`, `.article` → `GeneralNewsExtractor` fallback.
- **Noise:** `_clean_sina_body` breaks at `_SINA_TAIL_MARKERS` (特别声明 / 版权所有 /
  相关新闻 / 阅读排行榜 / 责任编辑 …) and drops exact rows in `_SINA_NOISE_EXACT`
  (新浪看点 / 官方账号 / 分享工具 / 面包屑 …).

## NetEase 网易新闻

- **Hot board:** `GET https://gw.m.163.com/nc-main/api/v1/hqc/no-repeat-hot-list`
- **Search:** `GET https://www.163.com/search?keyword=<kw>`
- **Article URL template:** `https://www.163.com/dy/article/{docid}.html`
- **Response family:** JSON, guard `code in (0, "0", 200, "200")`, rows at `data.items[]`,
  only rows with `type == "doc"`.
- **Row fields:** `contentId`, `title`, `hotValue`, `click`, `commentCount`, `votecount`,
  `threadVote`, `ptime`, `source`.
- **Heat metrics:** `hot_value` 0.40 + `click` 0.30 + `comments` 0.15 + `votes` 0.10 +
  `thread_votes` 0.05; `comments` floor 10.
- **Detail selectors:** `.post_body`, `#endText`, `.post_text` → GNE fallback.
- **Search parser:** `_SearchCardParser` tracks `li.keyword_new_list` (legacy) or
  `div.keyword_new → h3` (live), with a conservative `<a href=.../dy/article/...>` regex
  fallback; explicitly returns `[]` on "keyword_list empty" to avoid treating recommendations
  as results. De-duplicates by docid.

## The Paper 澎湃新闻

- **Hot board:** `GET https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar`
- **Search:** `POST https://api.thepaper.cn/search/web/news` with
  `word, orderType=3, pageNum, pageSize, searchType=1`, headers `client-type: 1`.
- **Article URL template:** `https://www.thepaper.cn/newsDetail_forward_{cont_id}`
- **Response family:** JSON; hot rows probed across paths
  `data.hotNews.contList` / `data.hotNews` / `data.hotList` / `data.associateContList` /
  `data.list` (`_ROW_PATHS`). **Known drift surface** — this endpoint has historically
  moved its row list between these locations.
- **Row fields:** `contId`, `name`, `summary`, `interactionNum`, `praiseTimes`,
  `pubTimeLong`, `contType` (must be 0), `paywalled` (skip if true).
- **Heat metrics:** `interaction_num` 0.60 (floor 1.0) + `praise_times` 0.40 (floor 10).
- **Drift policy:** unknown `code` → empty capture (degrade to `partial`, not crash);
  `_schema_warning` reports a non-secret `code` string into `metadata["schema_warning"]`.
- **Detail extraction chain:** `__NEXT_DATA__` JSON `articleBody` → DOM selectors → GNE.

## Juejin 掘金

- **Hot rank:** `GET https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot`
- **Detail:** `POST https://api.juejin.cn/content_api/v1/article/detail` with `article_id`
- **Search:** `POST https://api.juejin.cn/search_api/v1/search` with
  `key_word, id_type=0, page_no, page_size`
- **Response family:** JSON, guard `err_no == 0`, rows at `data[]`. Search nests one level
  deeper: `data[].result_model.article_info`.
- **Row fields:** `content_id`/`article_id`, `title`, `brief`, `ctime`, `hot_rank` /
  `hot_index`, counters `view, like, collect, comment_count, interact_count`.
- **Heat metrics:** `hot_rank`; engagement metrics `views / likes / collects / comments /
  interactions`.
- **Search constraint (spike-tested):** anonymous search returns **only the first page of
  20** — `page_no`, `page`, `cursor`, `search_after`, `page_size` are all ignored server-side.
  Design around single-page-per-keyword; expand volume via more keywords, not pagination.
- **Detail:** detail API `mark_content`/`content` → article page `article_text` →
  summary/title fallback.

## Adding a seventh platform

Copy the closest response-family pattern above, then fill in: endpoint, envelope guard,
row path, stable ID, heat fields, detail selectors, noise constants, drift behavior. Keep
the provider interface identical. See `authoring-playbook.md`.
