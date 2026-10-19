---
domain: codex
tier: L3
doc_status: active-ssot
related:
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\subskills\S31A_数据源探针与路线选型\SKILL.md
  - @@GENERAL_ROOT:win@@\assets\skills\S31_爬虫策略探勘与选型\SKILL.md
birth_ceremony_id: bc-openclicap-f3b14a2c
birth_ceremony_date: 2026-05-19
---

# OpenCLI 能力全景速查表

> 版本快照：813 命令 / 136 站点适配器 / 7 桌面应用适配器 / 12 外部 CLI
> 生成时间：2026-05-19

---

## 一、它在 S31 里的定位

S31 的探针优先级：**O0 → A → A1 → B**

opencli 就是 **O0**。意思是：碰到任何抓数据的需求，第一反应不是写爬虫，而是先查"opencli 有没有现成的"。有就直接用，没有再往下降级。

```
你的任务："帮我查一下小红书上关于 AI 玩具的笔记"

❌ 以前：写 Playwright 脚本 → 模拟登录 → 解析 DOM → 调试半天
✅ 现在：opencli xiaohongshu search "AI玩具" --limit 5 -f json → 5 秒出结果
```

---

## 二、136 个站点适配器分类速查

### 🛒 电商与消费
| 站点 | 关键词 | 典型用途 |
|:---|:---|:---|
| taobao | 淘宝 | 搜商品、比价 |
| jd | 京东 | 搜商品 |
| 1688 | 阿里巴巴批发 | 供应链选品 |
| xianyu | 闲鱼 | 二手市场行情 |
| amazon | 亚马逊 | 跨境电商调研 |
| coupang | 韩国电商 | 海外市场 |
| smzdm | 什么值得买 | 消费决策参考 |
| dianping | 大众点评 | 本地生活/餐饮 |
| ctrip | 携程 | 旅游酒店 |
| ke | 贝壳找房 | 房产数据 |

### 📱 社交与内容平台（国内）
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| xiaohongshu | 小红书 | 搜笔记、评论、创作者数据、下载图片视频、发布笔记 |
| rednote | 小红书(别名) | 同上 |
| bilibili | B站 | 搜视频、弹幕、UP主数据 |
| douyin | 抖音 | 搜视频、评论 |
| weibo | 微博 | 热搜、博文、评论 |
| zhihu | 知乎 | 热榜、问答、文章导出、收藏夹 |
| tieba | 百度贴吧 | 搜帖子 |
| douban | 豆瓣 | 影评、书评、小组 |
| hupu | 虎扑 | 体育社区 |
| v2ex | V2EX | 技术社区 |
| jike | 即刻 | 社交动态 |
| zsxq | 知识星球 | 付费社群内容 |
| toutiao | 今日头条 | 新闻资讯 |
| weixin | 微信公众号 | 公众号文章 |

### 📱 社交与内容平台（海外）
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| twitter | X/推特 | 搜推文、时间线 |
| reddit | Reddit | 搜帖子、评论 |
| youtube | YouTube | 搜视频、字幕、评论、频道、订阅管理 |
| tiktok | TikTok | 搜视频 |
| instagram | Instagram | 搜帖子 |
| facebook | Facebook | 搜帖子 |
| linkedin | LinkedIn | 职业社交 |
| bluesky | Bluesky | 搜帖子 |
| medium | Medium | 博客文章 |
| substack | Substack | Newsletter |
| pixiv | Pixiv | 二次元插画 |

### 💰 财经与投资
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| xueqiu | 雪球 | K线、股票行情、热门讨论、基金快照、自选股 |
| eastmoney | 东方财富 | A股行情 |
| sinafinance | 新浪财经 | 财经新闻 |
| tdx | 通达信 | 行情数据 |
| ths | 同花顺 | 行情数据 |
| yahoo-finance | 雅虎财经 | 美股行情 |
| binance | 币安 | 加密货币 |
| coingecko | CoinGecko | 币价聚合 |
| defillama | DeFi | DeFi 数据 |
| longbridge | 长桥(外部CLI) | AI 原生行情+交易 |
| barchart | Barchart | 商品期货 |

### 🎓 学术与研究
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| google-scholar | 谷歌学术 | 搜论文 |
| baidu-scholar | 百度学术 | 搜论文 |
| arxiv | Arxiv | 预印本论文 |
| cnki | 知网 | 中文学术 |
| wanfang | 万方 | 中文学术 |
| pubmed | PubMed | 医学论文 |
| openalex | OpenAlex | 学术元数据 |
| openreview | OpenReview | 论文评审 |
| paperreview | PaperReview | 论文评审 |
| dblp | DBLP | 计算机文献 |
| zlibrary | Z-Library | 电子书搜索下载 |

### 👨‍💻 开发者工具
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| gh | GitHub(外部CLI) | 仓库、Issue、PR、Release |
| gitee | Gitee | 国内 Git 平台 |
| stackoverflow | StackOverflow | 技术问答 |
| npm | NPM | Node 包注册表 |
| pypi | PyPI | Python 包注册表 |
| maven | Maven | Java 包注册表 |
| crates | Crates.io | Rust 包注册表 |
| nuget | NuGet | .NET 包注册表 |
| rubygems | RubyGems | Ruby 包注册表 |
| packagist | Packagist | PHP 包注册表 |
| goproxy | GoProxy | Go 包注册表 |
| homebrew | Homebrew | macOS 包管理 |
| flathub | Flathub | Linux 应用商店 |
| dockerhub | DockerHub | 容器镜像 |
| hackernews | HN | 技术社区 |
| lobsters | Lobsters | 技术社区 |
| linux-do | Linux.do | Linux 社区 |
| devto | Dev.to | 技术博客 |
| mdn | MDN | Web 文档 |
| rfc | RFC | 网络标准 |
| endoflife | EndOfLife | 软件生命周期 |
| nvd | NVD | 漏洞数据库 |
| osv | OSV | 开源漏洞 |
| oeis | OEIS | 整数数列 |

### 🏢 办公协同（私域）
| 工具 | 类型 | 典型能力 | 当前状态 |
|:---|:---|:---|:---|
| lark-cli | 外部CLI | 飞书全量：消息、文档、表格、日历、任务，200+命令 | ✅ 已安装 |
| dws | 外部CLI | 钉钉：消息、文档、日历、通讯录 | ⬜ 待安装 |
| wecom-cli | 外部CLI | 企业微信：通讯录、待办、会议、消息、日历 | ⬜ 待安装 |
| wx | 外部CLI | 微信：会话、消息搜索、联系人、导出 | ⬜ 待安装 |
| tg | 外部CLI | Telegram：MTProto 协议同步、搜索、导出 | ⬜ 待安装 |
| discord | 外部CLI | Discord：本地 SQLite 同步搜索导出 | ⬜ 待安装 |
| ntn | 外部CLI | Notion：页面、数据库、搜索、评论 | ⬜ 待安装 |
| obsidian | 外部CLI | Obsidian：笔记、搜索、标签、任务、同步 | ⬜ 待安装 |

### 🤖 AI 平台
| 站点 | 关键词 | 典型能力 |
|:---|:---|:---|
| chatgpt | ChatGPT | 对话 |
| claude | Claude | 对话 |
| deepseek | DeepSeek | 对话 |
| gemini | Gemini | 对话 |
| grok | Grok | 对话 |
| qwen | 通义千问 | 对话 |
| doubao | 豆包 | 对话 |
| yuanbao | 腾讯元宝 | 对话、历史、状态 |
| jimeng | 即梦 | AI 绘图 |
| notebooklm | NotebookLM | AI 笔记 |
| hf | HuggingFace | 模型仓库 |
| yollomi | Yollomi | AI图片/视频生成、换脸、去背景、超分 |

### 🔍 搜索引擎
| 站点 | 关键词 |
|:---|:---|
| google | 谷歌搜索 |
| brave | Brave 搜索 |
| duckduckgo | DDG 搜索 |
| yahoo | 雅虎搜索 |

### 📰 新闻与媒体
| 站点 | 关键词 |
|:---|:---|
| reuters | 路透社 |
| bbc | BBC |
| bloomberg | 彭博 |
| 36kr | 36氪 |
| sinablog | 新浪博客 |

### 🎮 娱乐与生活
| 站点 | 关键词 |
|:---|:---|
| steam | Steam 游戏 |
| spotify | Spotify 音乐 |
| imdb | IMDB 影视 |
| tvmaze | 电视节目 |
| lichess | 国际象棋 |
| wttr | 天气查询 |
| weread | 微信读书 |
| xiaoyuzhou | 小宇宙播客 |
| apple-podcasts | Apple 播客 |

### 🏛️ 政府与法规
| 站点 | 关键词 |
|:---|:---|
| gov-law | 中国法规 |
| gov-policy | 中国政策 |
| openfda | 美国FDA |
| rest-countries | 国家信息 |
| wikidata | 维基数据 |
| wikipedia | 维基百科 |

### 💼 求职与招聘
| 站点 | 关键词 |
|:---|:---|
| boss | Boss直聘 |
| 51job | 前程无忧 |
| indeed | Indeed |
| maimai | 脉脉 |
| nowcoder | 牛客 |
| 1point3acres | 一亩三分地 |

### 📐 设计资源
| 站点 | 关键词 |
|:---|:---|
| uisdc | 优设 |
| uiverse | UIverse |

### 🖥️ 桌面应用适配器（7个，通过 CDP 协议控制）
| 应用 | 能力 |
|:---|:---|
| antigravity | 控制 Antigravity IDE |
| cursor | 控制 Cursor IDE（Composer/聊天/终端） |
| codex | 控制 Codex |
| chatgpt-app | 控制 ChatGPT 桌面版 |
| chatwise | 控制 ChatWise |
| discord-app | 控制 Discord 桌面版 |
| doubao-app | 控制豆包桌面版 |

---

## 三、Browser Bridge 通用命令

除了站点适配器，opencli 还有一套**通用浏览器操控命令**（`opencli browser`），可以在任何网页上执行：

| 命令 | 作用 |
|:---|:---|
| `open` | 打开 URL |
| `click` | 点击元素 |
| `fill` / `type` | 填写表单 |
| `extract` | 提取页面内容 |
| `screenshot` | 截图 |
| `scroll` | 滚动页面 |
| `eval` | 执行 JavaScript |
| `wait` | 等待元素出现 |
| `network` | 抓取网络请求 |
| `analyze` | 分析页面结构 |

这意味着即使某个冷门网站没有专用适配器，你仍然可以用这些通用命令手动编排一套采集流程——相当于一个命令行版的 Playwright。

---

## 四、与 S31 的协同关系总结

```
S31 探针优先级：

O0 ← opencli 的 136 站点适配器 + 12 外部 CLI + Browser Bridge
 ↓ （opencli 拿不到时才降级）
 A ← requests + F12 抓包
 ↓
A1 ← SSR JSON 剥离（__NEXT_DATA__）
 ↓
 B ← Playwright / DrissionPage 兜底
```

Agent 拿到任何爬取任务时的标准动作：
1. **强制先查本表 (`view_file` 查阅本文件)**，看目标站点有没有 opencli 适配器。
2. 有 → 直接 `opencli <site> <action> -f json`，拿到数据。
3. 没有 → 降级到 A/A1/B，按 S31 法典走。
