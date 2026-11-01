# ✨ 外链预览 | Link Preview (AstrBot Plugin)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-v4.16%2B-brightgreen)
![Platform](https://img.shields.io/badge/平台-QQ%20%7C%20OneBot-12B7F5)
![Render](https://img.shields.io/badge/渲染-Playwright%20Chromium-2EAD33)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✅ 简介 | Introduction

<table>
  <tr>
    <td width="190" align="center">
      <img width="170" alt="Link Preview logo" src="docs/images/logo.png" style="border-radius: 24px;" />
    </td>
    <td>
      <strong>Link Preview · 外链预览</strong><br />
      YouTube · TikTok · X · pixiv · Wikipedia<br />
      <sub>群里发一条链接，回一张排版好的卡片图。</sub>
    </td>
  </tr>
</table>

这是一个为 **AstrBot** 编写的插件：群聊里有人发国外平台的链接时，自动抓取标题、作者、正文、配图、数据和热门评论，用 Playwright 在本地渲染成一张卡片图片发回群里。

[![Stars](https://img.shields.io/github/stars/EndermanMYR/astrbot_plugin_link_preview?color=yellow&label=%E6%A0%87%E6%98%9F)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/stargazers)
[![Issues](https://img.shields.io/github/issues/EndermanMYR/astrbot_plugin_link_preview?color=darkgreen&label=%E5%8F%8D%E9%A6%88)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/EndermanMYR/astrbot_plugin_link_preview?color=blue&label=%E8%AF%B7%E6%B1%82)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/EndermanMYR/astrbot_plugin_link_preview?color=blueviolet&label=%E6%9C%80%E8%BF%91%E6%9B%B4%E6%96%B0)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/commits/main)

> [!IMPORTANT]
> 卡片由容器内的 **Playwright Chromium** 在本机渲染，不走第三方截图接口。浏览器不可用时会自动退回 AstrBot 自带的文转图服务，此时排版会有差异。

## ✅ 功能列表 | Features

- **自动识别**：群消息里出现链接就自动出卡片，不需要 @ 或指令
- **19 个平台**：YouTube、TikTok、Instagram、X、GitHub、Bluesky、pixiv、Steam、Reddit、维基百科、维基文库、Dailymotion、niconico、Spotify、Vimeo、SoundCloud、Threads、Twitch、Facebook
- **热门评论**：YouTube、TikTok、X、GitHub Issue/PR、Bluesky、pixiv 的卡片会附带几条高赞评论
- **评论单独看**：`/评论` 出一张只放评论的卡，最多 10 条
- **维基全文**：`/全文` 把词条或维基文库作品分页渲染，合并转发发出，中文按简体显示
- **敏感词屏蔽**：内置约 150 个政治敏感词，中文支持插字写法识别，命中的评论单独剔除
- **R18 过滤**：词表 + 平台敏感标记双重判断，命中整条不发
- **出站检查**：机器人自己要发的消息（含合并转发里的文字）也会在发送前过一遍词表
- **按群开关配图**：`/预览图片` 让管理员单独控制本群卡片是否显示配图
- **深色/浅色主题**：一张配置切换
- **去重**：同一链接在同一个群里 30 秒内只预览一次

<table>
  <tr>
    <td width="50%" align="center" valign="top"><img alt="YouTube 视频卡片，带播放量、点赞和热门评论" src="docs/images/card-youtube.jpg" /></td>
    <td width="50%" align="center" valign="top"><img alt="GitHub 仓库卡片" src="docs/images/card-github.jpg" /></td>
  </tr>
  <tr>
    <td width="50%" align="center" valign="top"><img alt="Steam 游戏卡片，带价格、推荐数和标签" src="docs/images/card-steam.jpg" /></td>
    <td width="50%" align="center" valign="top"><img alt="浅色主题下的维基百科词条卡片" src="docs/images/card-light.jpg" /></td>
  </tr>
</table>

## 🌐 平台支持 | Platforms

| 平台 | 抓取内容 | 评论 |
|---|---|---|
| YouTube | 标题、频道、简介、封面、时长、播放/点赞 | ✔ 热门评论 |
| TikTok | 视频封面或图集、作者、播放/点赞/评论/分享/收藏 | ✔ 按点赞排序 |
| Instagram | 帖子和 Reels 的作者、配文、图片（通过公开的嵌入修复站读取） | ✘ 需要登录 |
| X / Twitter | 正文、作者、配图、引用帖、回复/转帖/喜欢/浏览 | ✔ 借用 X 搜索插件的已登录浏览器（较慢，自动预览最多等 15 秒） |
| GitHub | 仓库、Issue、PR、用户主页 | ✔ Issue/PR 评论 |
| Bluesky | 正文、作者、配图、互动数 | ✔ 按点赞排序的回复 |
| pixiv | 标题、作者、标签、数据（R-18 不显示图片） | ✔ |
| Reddit | 标题、作者、版块 | ✘ 服务器访问被拦 |
| Steam | 名称、简介、价格、类型、推荐数 | ✘ 评测接口被拦 |
| 维基百科 | 词条摘要、配图 | — |
| 维基文库 | 作品名、作者、朝代、出处、开头正文；整部书的目录页显示章节列表 | — |
| Dailymotion | 标题、作者、封面、时长、播放/点赞、标签 | — |
| niconico | 标题、作者、封面、时长、播放/评论/收藏、标签 | — |
| Spotify / Vimeo / SoundCloud | 标题、作者、封面 | — |
| Threads / Twitch / Facebook | 页面元信息（要登录的页面不发） | — |

不在列表里的网址，用 `/预览 链接` 会按普通网页抓 OpenGraph 信息。

## 📦 安装 | Installation

将插件目录放入：

```
AstrBot/data/plugins/astrbot_plugin_link_preview
```

重启 AstrBot 后即可在 WebUI 中看到插件。

容器需要 Chromium 的系统依赖，否则渲染会一路退回文转图：

```bash
python -m playwright install-deps chromium
# emoji 显示需要
apt install -y fonts-noto-color-emoji
```

## ⚙️ 配置 | Configuration

插件使用 `_conf_schema.json` 定义配置，入口：

```
AstrBot WebUI -> 插件 -> 插件配置
```

### 🔧 基础

| 配置项 | 说明 |
|--------|------|
| `enabled` | 启用自动识别 |
| `platforms` | 分平台开关，默认全开 |
| `max_links_per_message` | 一条消息最多预览几个链接，默认 `2` |
| `dedupe_seconds` | 同一链接在同一个群里多久内不重复预览，默认 `30` |
| `private_enabled` | 私聊里也自动识别，默认关 |
| `group_whitelist` / `group_blacklist` | 只在这些群 / 不在这些群自动识别 |

### 🎨 卡片外观

| 配置项 | 说明 |
|--------|------|
| `theme` | 卡片主题：`dark` / `light` |
| `text_length` | 正文最多显示多少字，默认 `420` |
| `show_images` | 显示配图和封面 |
| `blur_sensitive` | 平台标记为敏感的图片自动模糊 |
| `comment_count` | 卡片里显示几条热门评论，默认 `3`，最大 `10` |

### 🌐 网络与抓取

| 配置项 | 说明 |
|--------|------|
| `proxy` | 访问国外平台用的代理，如 `http://127.0.0.1:7890` |
| `github_token` | GitHub Token（可选），提高 API 限额 |
| `fetch_timeout` | 抓取超时（秒），默认 `12` |
| `render_timeout` | 渲染超时（秒），默认 `25` |

### 🐦 X 评论

| 配置项 | 说明 |
|--------|------|
| `x_comments` | X 帖子也抓评论 |
| `x_comments_wait` | 自动预览时 X 评论最多等几秒，默认 `15` |
| `x_browser_url` / `x_browser_token` | X 浏览器服务地址和 Token；留空则读取 X 搜索插件的配置 |

### 📖 维基全文

| 配置项 | 说明 |
|--------|------|
| `full_page_chars` | 每页大约多少字，默认 `3500` |
| `full_max_pages` | 最多发几页，默认 `15` |

### 🛡️ 屏蔽

| 配置项 | 说明 |
|--------|------|
| `block_enabled` | 启用敏感词屏蔽 |
| `block_words_file` | 词表文件，默认 `data/sensitive_words/political.txt` |
| `block_words` | 额外屏蔽词 |
| `block_mode` | 命中后怎么处理：`整条不发` / `打码后发送` |
| `block_outgoing` | 机器人自己的回复也检查，默认开 |
| `r18_enabled` | 启用 R18 过滤 |
| `r18_block_flagged` | 平台标记为敏感的也整条不发 |
| `r18_words_file` | R18 词表，默认 `data/sensitive_words/r18.txt` |
| `r18_outgoing` | 机器人自己的回复也查 R18，默认关 |
| `block_notice` | 被拦截或发不出去时在群里提醒 |

## 📌 使用说明 | Usage

### 💬 指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/预览 链接` | `/preview` | 手动预览任意网页，不受平台开关限制 |
| `/评论 [链接]` | `/comments`、`/看评论` | 单独看评论（最多 10 条），不带链接时用本群最近预览的那条 |
| `/全文 [维基链接]` | `/fulltext`、`/维基全文` | 维基百科词条或维基文库作品全文，分页后合并转发 |
| `/预览图片 [开/关/默认]` | `/previewimg`、`/预览配图` | 管理员切换本群卡片是否显示配图和封面 |
| `/预览帮助` | `/previewhelp` | 查看帮助 |

> [!NOTE]
> `/全文` 的合并转发只有 QQ（OneBot / aiocqhttp）支持，其他平台会逐张发送。每页约 3500 字，最多 15 页，超出部分会提示看原文。

### 🛡️ 敏感词与 R18

- 词表文件默认是 `data/sensitive_words/political.txt`（相对 AstrBot 工作目录），第一次加载时用插件自带的 `sensitive_words.txt` 创建，之后改这个文件即可，改完立即生效
- 自带词表约 150 个政治敏感词（简繁体），刻意避开了「64」「民主」这类会大量误伤的短词
- 中文词去掉空格、间隔号、星号等插字后匹配；英文词按整词匹配
- 正文、标题、作者命中：默认整条不发，也可以设成打码后发送；评论命中只去掉那一条
- 按账号屏蔽：X 帖子作者的简介（和所在地）里带敏感词或 R18 词，不管这条帖子发的是什么都不预览
- X 搜索插件的 `political_keywords_file` 指向同一个文件，两个插件共用一份词表
- 维基 `/全文` 不做 R18 检查；机器人自己的回复默认也不查（`r18_outgoing`）

### 📤 发不出去时

- 命中屏蔽词：链接卡片、`/全文` 和机器人自己的回复都会在群里提醒一句（`block_notice`，默认开）
- 卡片被 QQ 拒收（比如图片没过 QQ 审核）：改发一句文字提醒

## 🧭 网络代理建议 | Network Proxy

插件要访问的多数平台在境外，服务器直连大概率超时。推荐给 Clash 加一条规则，或在配置里直接填 `proxy`：

```yaml
mixin:
  mode: rule

  proxy-groups:
    - name: LINK-PREVIEW
      type: select
      proxies:
        - HK   # ← 改成你的节点
        - DIRECT

  rules:
    - DOMAIN-SUFFIX,youtube.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,ytimg.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,tiktokcdn.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,twitter.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,x.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,twimg.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,bsky.app,LINK-PREVIEW
    - DOMAIN-SUFFIX,pixiv.net,LINK-PREVIEW
    - DOMAIN-SUFFIX,pximg.net,LINK-PREVIEW
    - DOMAIN-SUFFIX,dailymotion.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,niconico.com,LINK-PREVIEW
    - DOMAIN-SUFFIX,githubusercontent.com,LINK-PREVIEW

    - MATCH,DIRECT
```

> [!TIP]
> 维基百科、维基文库、GitHub、Steam 国内多数网络可直连，不必走代理；只把上面这些走代理能省不少流量。

## 🧪 开发验证 | Development

插件不依赖 AstrBot 就能单独跑抓取和渲染，方便调模板：

```bash
pip install httpx jinja2 playwright
python -m playwright install chromium
```

抓取一张卡片并渲染成图片：

```python
import asyncio, fetchers, render
from playwright.async_api import async_playwright

async def main():
    async with fetchers.make_client(None, 15) as c:
        card = await fetchers.fetch(c, "github",
            "https://github.com/EndermanMYR/astrbot_plugin_link_preview", comments=3)
        card = await render.prepare(c, card)
    html = render.build_html(card, "dark")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 680, "height": 900}, device_scale_factor=2)
        await pg.set_content(html, wait_until="load")
        await pg.evaluate("document.fonts.ready")
        el = await pg.query_selector("#card")
        await el.screenshot(path="card.jpg", type="jpeg", quality=92)
        await b.close()

asyncio.run(main())
```

`fetchers.py` 和 `render.py` 都不 import `astrbot`，可以直接在本地改模板看效果。上面 `docs/images/` 里的展示图就是这么生成的。

## ❤️ 致谢 | Credits

- 卡片渲染基于 [Playwright](https://playwright.dev/)
- 抓取基于 [httpx](https://www.python-httpx.org/)，模板基于 [Jinja2](https://jinja.palletsprojects.com/)
- X 评论借用 X 搜索插件提供的已登录浏览器服务

## 📜 许可证 | License

本项目基于 [MIT License](LICENSE) 发布，可自由使用、修改和分发，保留版权声明即可。

[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
