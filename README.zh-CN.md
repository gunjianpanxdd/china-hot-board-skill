# China Hot Board Skill · 中文文档

> [English](README.md) · 中文

[![Skill](https://img.shields.io/badge/type-agent%20skill-blueviolet)](README.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-yellow)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![平台](https://img.shields.io/badge/平台-6%20源-orange)](#支持哪些平台)

**中文热榜采集 / 新闻聚合 / trending 数据归一化 agent skill。**

把今日头条、百度热搜、新浪新闻、网易新闻、澎湃新闻、掘金这 6 个来源各不相同的热榜，统一成一套严格可判定的 `HotItem` 契约——带热度证据、带正文校验、抗站点改版。**所有端点免登录、无需 Cookie。**

这不是一个"能爬"的脚本，而是一份从生产级采集器中提炼出来的**工程手册**：怎么接新平台、怎么解析异构响应、怎么清洗正文噪音、怎么定义热度阈值、站点改版了怎么优雅降级。给 agent 用，让它别再把每个网站的坑重新踩一遍。

---

## 快速开始：3 步用起来

### 第 1 步：安装

```bash
git clone https://github.com/gunjianpanxdd/china-hot-board-skill.git

# 复制到你所用 agent 的 skills 目录，例如：
cp -r china-hot-board-skill <你的项目>/.claude/skills/
# 或
cp -r china-hot-board-skill <你的项目>/.workbuddy/skills/
```

目录名 `china-hot-board-skill` 不用改——它和 `SKILL.md` 里的 `name` 字段一致。

### 第 2 步：确认 agent 已识别

重启 agent 会话，让元数据进入上下文。可以问一句验证：

```
你有哪些 skill？
```

能看到 `china-hot-board-skill` 就装好了。

### 第 3 步：直接说人话

```
帮我接一个新的热榜数据源，知乎热榜。
```

就这么一句。`description` 字段会自动触发，agent 按 SKILL.md 里的工作流走完全程。

---

## 怎么用：三种触发方式

| 方式 | 怎么写 | 适合场景 |
|---|---|---|
| **自然语言**（推荐） | 直接描述任务 | 日常使用，最省事 |
| **@ 显式引用** | `@skill:china-hot-board-skill` + 问题 | 怕没触发、或多 skill 环境下点名 |
| **slash 命令** | `/china-hot-board-skill` | 终端式调用 |

### 自然语言触发：这样问最灵

`description` 里写好了触发词，下面这些说法都能命中：

```
# 加新平台
"接一个新的热榜平台：知乎"
"给我们的采集器加一个微博热搜源"

# 排查故障
"百度热搜采集返回空列表，帮我定位"
"澎湃那条为什么是 partial 状态"

# 写解析器
"给我写一个解析 JSONP 热榜的 parser"
"这个 HTML 里的 <!--s-data--> 怎么提取榜单"

# 定规则 / 清洗
"新平台的热度阈值应该怎么设"
"正文里全是导航和页脚噪音，怎么清洗"
```

**触发词的规律**：句子里出现「热榜 / 新闻源 / 采集 / 解析 / 热度 / partial / JSONP / 正文清洗」这类词，命中率最高。纯说"帮我爬个网站"太泛，不一定触发。

### 显式引用：多 skill 环境用这个

```
@skill:china-hot-board-skill 帮我看下掘金榜单为什么只有 20 条
```

### slash 命令

```
/china-hot-board-skill
```

---

## 实战：接一个新平台的完整流程

这是这个 skill 最核心的用法。你只需要提需求，agent 会按 8 步走：

**你的提问**
```
帮我接一个知乎热榜的数据源，要求和其他平台输出格式一致。
```

**agent 会依次做**

1. **匿名探测端点** —— 确认不需要 Cookie（需要就停下来，这个 skill 只管匿名源）
2. **判断响应族** —— JSON / JSONP / HTML 内嵌 / 搜索 DOM，四选一
3. **复制对应骨架** —— 从 `scripts/provider_template.py` 取模板
4. **归一化每一行** —— 产出 `HotItem`，稳定 `item_id`，所有平台专属字段塞进 `raw_payload`
5. **写正文提取兜底链** —— 原生选择器 → JSON-LD → GeneralNewsExtractor → reject
6. **做降级而非崩溃** —— 响应结构变了就返回 `partial` + `schema_warning`，不影响其他平台
7. **定热度规则** —— `weights` 分位打分 + `absolute_floors` 兜底
8. **跑校验脚本** —— 离线 fixture 验证 ID 稳定性和 metrics 非空

**依据的文档**（agent 会按需加载，不会一次性全塞进上下文）：

| 步骤 | 加载什么 |
|---|---|
| 1–2 | `references/platform-catalog.md`（6 平台的端点与响应族范例） |
| 3–5 | `scripts/provider_template.py` + `references/authoring-playbook.md` |
| 6–7 | `references/data-contract.md` + `references/scoring-and-ranking.md` |
| 8 | `scripts/verify_provider.py` |

---

## 怎么用：校验脚本（命令行）

`scripts/verify_provider.py` 可以**不联网**验证你的 provider 解析结果。三种检查：条目非空、`item_id` 稳定、`heat.metrics` 非空；喂两个 fixture 时还会比对 ID 集合是否漂移。

### 模式 A：检查已归一化的 items（最简单）

准备一个 JSON 文件，内容是数组，或 `{"items": [...]}`：

```json
[
  {
    "item_id": "zhihu_a1",
    "platform": "zhihu_hot",
    "title": "示例标题",
    "url": "https://example.com/1",
    "rank": 1,
    "heat": {"metrics": {"hot_value": 100}}
  }
]
```

运行：

```bash
python scripts/verify_provider.py --fixture resp.json
```

输出：

```
[OK] resp.json: 1 items, 0 missing id, 0 without metrics
```

### 模式 B：检查你写的 provider 类

把站点原始响存成文件（**原样保存**，别改格式），然后指到你的 `.py`：

```bash
python scripts/verify_provider.py \
  --fixture baidu_raw.html \
  --module my_provider.py \
  --class BaiduHotProvider \
  --parser parse_hot_list \
  --platform baidu_hot
```

参数说明：

| 参数 | 必填 | 说明 |
|---|---|---|
| `--fixture` | 是 | 保存的原始响应，可重复传多个做稳定性比对 |
| `--module` | 否 | provider 所在的 `.py` 路径；不给就是模式 A |
| `--class` | 给 module 时必填 | provider 类名 |
| `--parser` | 否 | 解析方法名，默认 `parse_hot_list`（签名 `(raw_text, collected_at)`） |
| `--platform` | 否 | 报告里显示的平台名 |

多 fixture 比对：

```bash
python scripts/verify_provider.py --fixture day1.json --fixture day2.json --module my_provider.py --class MyProvider
```

### 怎么看结果 / 退出码

- `[OK]` 通过；`[FAIL]` 有问题；`[WARN]` ID 集合变了（榜单本来就会变，属于提示不是错误）
- 退出码 `0` 全通过 / `1` 校验失败 / `2` provider 导入或参数错误
- 依赖很轻：只需要标准库 + 你 provider 自身需要的包（如 `httpx`）

---

## 怎么用：复用 provider 模板

`scripts/provider_template.py` 是可直接复制的骨架，实现了完整接口：

```python
class MySourceProvider:
    platform = "my_source"
    weights = {...}            # 分位打分权重
    absolute_floors = {...}    # 动态下限失效时的兜底

    @staticmethod
    def parse_hot_list(raw_text: str, collected_at: str) -> ProviderCapture: ...
    def fetch_detail(self, item: HotItem) -> HotItem: ...
    # 可选：search() / enrich_metrics()
```

复制后改三处即可：**端点 URL**、**响应解析**、**热度字段映射**。契约部分（`ProviderCapture` / `HotItem` / 三条不变量）别动——改了就失去"和其他平台输出一致"的意义。

---

## 你会得到什么：数据契约

每个 provider 返回 `ProviderCapture(raw_text, raw_suffix, items, metadata)`，其中每项是不可变的 `HotItem`：

```
item_id · platform · title · url · rank · heat(HeatMetrics)
· summary · publication_time · collected_at · raw_payload
```

三条不变量，把它和普通爬虫区分开：

1. **严格成功契约** —— 响应结构对不上就抛 `ProviderContractError`，绝不悄悄塞垃圾行。已识别的改版可降级为 `partial` + `schema_warning`。
2. **热度必须有证据** —— `HeatEvidence` 至少带一个正向信号（榜单排名 / 原生热度值 / 具名互动量），不允许静默给 0。
3. **正文必须校验** —— `validate_full_text` 检查字数（原生 80 / GNE 兜底 200）、段落或句子数、页面噪音命中数，不达标就标记 `rejected` / `summary` / `title_only`。

详见 [`references/data-contract.md`](references/data-contract.md)。

---

## 支持哪些平台

| 平台 | 端点类型 | 热度信号 |
|---|---|---|
| 今日头条 | JSON 热榜 API | `HotValue` |
| 百度热搜 | HTML `<!--s-data-->` | `hotScore` |
| 新浪新闻 | JSONP `GetTopDataList.php` | `top_num` + 评论数 |
| 网易新闻 | JSON hot-list API | 热度/点击/评论/投票混合 |
| 澎湃新闻 | JSON (`cache.thepaper.cn`) | 互动 + 点赞 |
| 掘金 | JSON 排行 API | `hot_rank` + 互动量 |

端点、响应形状、噪音常量、schema 漂移特征全在 [`references/platform-catalog.md`](references/platform-catalog.md)。

---

## 这个 skill 不做什么

| 不做 | 原因 |
|---|---|
| 定时任务 / APScheduler | 属于宿主服务的运行时 |
| Redis 锁 / 开关 / Cookie 池 | 同上，且本 skill 只管匿名源 |
| PG 入库 / upsert | 存储策略因项目而异 |
| 代理池 / 验证码破解 | 合规红线，遇到门槛应降级并触发合规审查 |

**它装的是"怎么接、怎么维护一个数据源"的经验，不是运行时服务本身。** 想让 agent 能编排你的采集能力，正解是给服务加 MCP 出口，而不是把它塞进 skill。

---

## 验证状态（如实说明）

已在本仓库实测：

- `quick_validate` 结构校验：**通过**
- 两个脚本 `py_compile`：**通过**
- fixture 离线冒烟测试：**通过**（2 items / 0 缺 ID / 0 缺 metrics）
- 打包为 zip：**成功**

**未做**：实网抓取 6 个平台的端到端测试（会触发站点限流，且端点随时可能变）；装进具体 agent 后的自动触发测试（依赖你的环境）。请在自己的环境里验证这两项——`references/platform-catalog.md` 里的端点记录的是采集时的形态，站点改版是正常的。

---

## 目录结构

```
china-hot-board-skill/
├── SKILL.md                     # 触发词、工作流、三条不变量、接平台 8 步、排障
├── README.md                    # English
├── README.zh-CN.md              # 本文
├── LICENSE                      # MIT
├── references/
│   ├── platform-catalog.md      # 6 平台：端点、响应族、热度字段
│   ├── data-contract.md         # HotItem / HeatMetrics / HeatEvidence / 校验语义
│   ├── scoring-and-ranking.md   # 权重、绝对下限、动态分位、排序
│   └── authoring-playbook.md    # 接新平台 + 排障手册 + 反模式
└── scripts/
    ├── provider_template.py     # 带注释的 provider 骨架
    └── verify_provider.py       # 离线 fixture 校验器
```

## License

MIT — 见 [LICENSE](LICENSE)。

> 内置平台均为公开端点。使用前请遵守各站点的服务条款与 robots 政策；本 skill 用于组织和归一化公开可得的热度数据。
