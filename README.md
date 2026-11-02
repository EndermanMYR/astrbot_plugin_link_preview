# ✨ 外链预览 | Link Preview (AstrBot Plugin)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AstrBot](https://img.shields.io/badge/AstrBot-v4.16%2B-brightgreen)
![Platform](https://img.shields.io/badge/平台-QQ%20%7C%20OneBot-12B7F5)
![Render](https://img.shields.io/badge/渲染-AstrBot%20文转图-2EAD33)
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

这是一个为 **AstrBot** 编写的插件：群聊里有人发国外平台的链接时，自动抓取标题、作者、正文、配图、数据和热门评论，渲染成一张卡片图片发回群里。

[![Stars](https://img.shields.io/github/stars/EndermanMYR/astrbot_plugin_link_preview?color=yellow&label=%E6%A0%87%E6%98%9F)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/stargazers)
[![Issues](https://img.shields.io/github/issues/EndermanMYR/astrbot_plugin_link_preview?color=darkgreen&label=%E5%8F%8D%E9%A6%88)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/EndermanMYR/astrbot_plugin_link_preview?color=blue&label=%E8%AF%B7%E6%B1%82)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/EndermanMYR/astrbot_plugin_link_preview?color=blueviolet&label=%E6%9C%80%E8%BF%91%E6%9B%B4%E6%96%B0)](https://github.com/EndermanMYR/astrbot_plugin_link_preview/commits/main)

> [!IMPORTANT]
> 卡片渲染走 **AstrBot 自带的文转图服务**（`html_render`），插件不再依赖 Playwright、不用装 Chromium、也不用 Docker。代价是渲染依赖该服务，详见下方「渲染」一节。

> [!WARNING]
> 插件内置的屏蔽词**不可能覆盖所有敏感内容**，转发抓取内容存在账号被限制或封禁的风险。**使用前请阅读 [免责声明](#️-免责声明--disclaimer)，风险与合规责任由部署者自行承担。**

## ✅ 功能列表 | Features

- **自动识别**：群消息里出现链接就自动出卡片，不需要 @ 或指令
- **19 个平台**：YouTube、TikTok、Instagram、X、GitHub、Bluesky、pixiv、Steam、Reddit、维基百科、维基文库、Dailymotion、niconico、Spotify、Vimeo、SoundCloud、Threads、Twitch、Facebook
- **热门评论**：YouTube、TikTok、X、Instagram、GitHub Issue/PR、Bluesky、pixiv、Steam 的卡片会附带几条高赞评论
- **评论靠 Cookie**：X 需要登录态，填 `x_cookie` 即可，不用在服务器上跑浏览器登录
- **Steam 评测**：抓社区里最有帮助的评测，带推荐/不推荐、游玩时长和赞数；填了 Web API Key 还能显示当前在线人数
- **评论单独看**：`/评论` 出一张只放评论的卡，最多 10 条
- **维基全文**：`/全文` 把词条或维基文库作品分页渲染，合并转发发出，中文按简体显示
- **敏感词屏蔽**：内置约 150 个政治敏感词，中文支持插字写法识别，命中的评论单独剔除
- **R18 过滤**：词表 + 平台敏感标记双重判断，命中整条不发
- **出站检查**：机器人自己要发的消息（含合并转发里的文字）也会在发送前过一遍词表
- **按群开关配图**：`/预览图片` 让管理员单独控制本群卡片是否显示配图
- **竖图完整显示**：多图卡片默认是网格裁切（`object-fit: cover`），检测到竖图（高/宽 > 1.25，比如手机截图）会自动改成纵向堆叠，整张显示不裁
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
  <tr>
    <td width="50%" align="center" valign="top"><img alt="X 帖子卡片，带回复、转帖、喜欢数和三条热门评论" src="docs/images/card-x.jpg" /></td>
    <td width="50%" align="center" valign="top"><img alt="TikTok 视频卡片，带播放量、点赞、评论、分享、收藏" src="docs/images/card-tiktok.jpg" /></td>
  </tr>
</table>

## 🌐 平台支持 | Platforms

| 平台 | 抓取内容 | 评论 |
|---|---|---|
| YouTube | 标题、频道、简介、封面、时长、播放/点赞 | ✔ 热门评论 |
| TikTok | 视频封面或图集、作者、播放/点赞/评论/分享/收藏 | ✔ 按点赞排序 |
| Instagram | 帖子和 Reels 的作者、配文、图片（通过公开的嵌入修复站读取） | ✘ 实测拿不到，见下方说明 |
| X / Twitter | 正文、作者、配图、引用帖、回复/转帖/喜欢/浏览 | ✔ 需填 `x_cookie` + 浏览器服务（较慢，最多等 25 秒，可调） |
| GitHub | 仓库、Issue、PR、用户主页 | ✔ Issue/PR 评论（填 `github_token` 免限流） |
| Bluesky | 正文、作者、配图、互动数 | ✔ 按点赞排序的回复 |
| pixiv | 标题、作者、标签、数据（R-18 不显示图片） | ✔ |
| Reddit | 标题、作者、版块 | ✘ 机房 IP 会被拦（`hot.json` 直接 403），配 `proxy` 后正常 |
| Steam | 名称、简介、价格、类型、推荐数；填 `steam_api_key` 才有当前在线人数 | ✔ 热门评测（含推荐与否、游玩时长、赞数） |
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

### 🖼️ 渲染：走 AstrBot 的文转图

卡片不再由插件自己开浏览器截图，而是把 HTML 交给 AstrBot 的 `html_render`。所以：

- 插件**不依赖 Playwright**，`requirements.txt` 里没有它
- 不用装 Chromium、不用 `playwright install-deps`、不用 Docker
- 代价：渲染质量与可用性取决于文转图服务

> [!IMPORTANT]
> `t2i_strategy` 必须是 `remote`（默认值）。配成 `local` 时 AstrBot 会直接抛 `NotImplementedError`——本地策略只能画 Markdown，画不了 HTML，卡片会发不出去。

**服务不稳时**：官方端点 `t2i.soulter.top` 偶尔返回 503。插件对每次渲染重试 3 次（间隔 1.2 / 2.4 秒），仍失败就记一条 warning，这条链接不出卡片，其他链接不受影响。AstrBot 支持配置多个 t2i 端点，想自己托管改那里即可。

#### 出图质量

远端服务的视口固定 **800×720、DPR 1**，且忽略 `device_scale_factor`，所以做了三件事让效果接近本机渲染：

| 问题 | 处理 |
|---|---|
| 右侧一大片空白 | 模板加了 `body.t2i` 版式，卡片铺满 800 宽（原来 640） |
| 矮卡片下方留白 | 视口高度不会小于 720，出图后用 Pillow 按背景色裁掉多余边距 |
| 数字英文被撑成「2 0 2 6」 | 字体栈把 `DejaVu Sans` / `sans-serif` 排在 CJK 字体之前。远端机器没装 Noto CJK 时会退到 HanaMin 这类字体，它们的拉丁字形是全角的 |

超长卡片不会被截断——高度会随内容延伸。

> [!NOTE]
> 唯一的差距是分辨率：现在是 800 宽（裁完约 780），原来本机渲染是 1200 宽（600 CSS px × DPR 2）。文字像素高度相同，整图略小一点。

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
| `steam_api_key` | Steam Web API Key（可选），填了才显示 Steam 当前在线人数；评测不需要 Key |
| `fetch_timeout` | 抓取超时（秒），默认 `12` |
| `render_timeout` | 渲染超时（秒），默认 `25` |

### 🐦 X 评论

| 配置项 | 说明 |
|--------|------|
| `x_comments` | X 帖子也抓评论 |
| `x_comments_wait` | X 评论等待秒数，默认 `25`。**这个值同时决定出卡速度**：调小更快但可能抓不全，调大更完整但更慢（8=快，15=折中，25=完整）|
| `x_browser_url` / `x_browser_token` | 浏览器服务地址和 Token（抓取 X 评论用） |
| `x_cookie` | 从自己浏览器复制的 X Cookie，抓评论必需 |

X 卡片本身走公开接口，不需要登录；只有「热门评论」需要登录态。插件不替你登录 X，而是**用你自己浏览器里的 Cookie**——比在服务器上跑浏览器自动化稳，也不容易触发风控封 IP。

抓取后端随插件放在 [`x-browser-service/`](x-browser-service/README.md)，起一个容器即可：

```bash
cd x-browser-service
cp .env.example .env      # 填 Token，确认 Cookie 目录
docker compose up -d      # 本地构建，约 10 分钟（主要花在装 chromium）
```

不想等第一次构建的话，在 `.env` 里加 `XBROWSER_IMAGE=ghcr.io/endermanmyr/astrbot-xbrowser:latest` 就能直接拉预构建镜像。`ghcr.io` 在部分网络下不可达，连不上就用默认的本地构建。

再把地址和 Token 填进 `x_browser_url` / `x_browser_token`。不部署也不影响其他平台，只是 X 卡片没有评论。

> [!TIP]
> 不想用 Docker 也能跑：它就是普通的 aiohttp + Playwright 服务，可以用 systemd 裸机部署，详见 [x-browser-service/README.md](x-browser-service/README.md#不用-docker裸机--systemd)。

#### 🔑 Cookie 怎么来：从哪里拿

**前提：在电脑上操作**（手机浏览器看不到开发者工具），并且这个浏览器**已经登录了 x.com**。无痕/隐私窗口不行，关掉就没了。

1. 打开 <https://x.com>，确认右上角是你自己的头像，说明已登录
2. 按 `F12` 打开开发者工具（macOS 是 `Option + Command + I`）
3. 切到 **Application** 标签
   - Chrome / Edge：`Application`
   - Firefox：`Storage` → `Cookies`
   - Safari：先「设置 → 高级 → 显示网页开发者功能」，再按 `Option + Command + I`
4. 左侧展开 **Cookies** → 点 `https://x.com`
5. 在列表上方的过滤框输入 `auth_token`，找到这一行，双击 **Value** 列复制
   - 值是 40 位十六进制，形如 `1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b`
6. 过滤框改成 `ct0`，同样复制它的 Value
   - **这个是 160 位，很长，别复制漏了**
7. 把两个值拼成一行：

   ```
   auth_token=1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b; ct0=9f8e7d6c5b4a...
   ```

8. 粘进插件配置的 `x_cookie`，保存 → 在 WebUI 里重载插件（或重启 AstrBot）

> [!TIP]
> 只粘两条值也行，不用写 `auth_token=` 前缀，用分号或空格隔开即可。插件会自动识别。

**怎么确认成功**：群里发一个 X 帖子链接，卡片下面出现「热门评论」就说明 Cookie 生效了。没出来的话看日志有没有 `[LinkPreview] 已写入手填的 X Cookie`。

**Cookie 会过期**：改密码、在别处退出登录、太久不用都可能失效。表现是评论突然变空，重新按上面步骤复制一次即可。

### 📖 维基全文

| 配置项 | 说明 |
|--------|------|
| `full_page_chars` | 每页大约多少字，默认 `3500` |
| `full_max_pages` | 最多发几页，默认 `15` |

### 🛡️ 屏蔽

| 配置项 | 说明 |
|--------|------|
| `block_enabled` | 启用敏感词屏蔽 |
| `block_words_file` | 词表文件；留空用插件数据目录下的 `political.txt` |
| `block_words` | 额外屏蔽词 |
| `block_mode` | 命中后怎么处理：`整条不发` / `打码后发送` |
| `block_outgoing` | 机器人自己的回复也检查，默认开 |
| `r18_enabled` | 启用 R18 过滤 |
| `r18_block_flagged` | 平台标记为敏感的也整条不发 |
| `r18_words_file` | R18 词表；留空用插件数据目录下的 `r18.txt` |
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

- 词表默认放在插件数据目录：`data/plugin_data/astrbot_plugin_link_preview/political.txt`，第一次加载时用插件自带的 `sensitive_words.txt` 创建，之后改这个文件即可，改完立即生效
- 从旧版本升级时，如果插件数据目录里还没有词表、而旧位置 `data/sensitive_words/political.txt` 存在，会先复制一份过来再继续；旧文件保留不动
- 想放在别处，把 `block_words_file` 填成绝对路径或相对 AstrBot 工作目录的路径即可
- 自带词表约 150 个政治敏感词（简繁体），刻意避开了「64」「民主」这类会大量误伤的短词
- 中文词去掉空格、间隔号、星号等插字后匹配；英文词按整词匹配
- 正文、标题、作者命中：默认整条不发，也可以设成打码后发送；评论命中只去掉那一条
- 按账号屏蔽：X 帖子作者的简介（和所在地）里带敏感词或 R18 词，不管这条帖子发的是什么都不预览
- 维基 `/全文` 也做 R18 检查，词条正文命中 R18 词整条不发，不会打码后照发；政治敏感词命中时按 `block_mode` 处理
- 机器人自己的回复默认不查 R18（`r18_outgoing`）

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

`fetchers.py` 和 `render.py` 的日志走 `from astrbot.api import logger`，所以要在**装了 AstrBot 的环境**里跑——最省事的是进 AstrBot 容器：

```bash
docker exec -it astrbot bash
cd /AstrBot/data/plugins
```

抓取一张卡片，把 HTML 存下来看看排版：

```python
import asyncio, fetchers, render

async def main():
    async with fetchers.make_client(None, 15) as c:
        card = await fetchers.fetch(c, "github",
            "https://github.com/EndermanMYR/astrbot_plugin_link_preview", comments=3)
        card = await render.prepare(c, card)
    open("card.html", "w", encoding="utf-8").write(render.build_html(card, "dark"))

asyncio.run(main())
```

`build_html(card, theme, t2i=True)` 出来的就是交给文转图的完整 HTML，用浏览器打开就能看到最终版式（`t2i=False` 是原来的 640 宽版式）。`render.crop_image(path)` 用来裁掉远端服务留下的空白边距，可以单独拿一张图试。

### 单元测试

测试用标准库 `unittest`，不联网、不需要 AstrBot（`tests/_stub.py` 会在进程内伪造 `astrbot.api.logger`）：

```bash
python -m unittest discover -s tests -t . -v
```

覆盖的是容易悄悄坏掉的部分：链接识别（19 个平台）、数字/时长/时间格式化、OpenGraph 解析、全文分页、词表匹配（含插字写法）、配置项与抓取器是否对齐、发布包是否缺文件、模板字体栈顺序、裁边逻辑。CI 在 `.github/workflows/ci.yml`，推 main 就跑。

### 单元测试

测试用标准库 `unittest`，不联网、不需要 AstrBot（`tests/_stub.py` 会在进程内伪造 `astrbot.api.logger`）：

```bash
python -m unittest discover -s tests -t . -v
```

覆盖的是容易悄悄坏掉的部分：链接识别（19 个平台）、数字/时长/时间格式化、OpenGraph 解析、全文分页、词表匹配（含插字写法）、配置项与抓取器是否对齐、发布包是否缺文件。CI 在 `.github/workflows/ci.yml`，推 main 就跑。

## ❤️ 致谢 | Credits

- 卡片渲染基于 AstrBot 自带的文转图（`html_render`）
- 抓取基于 [httpx](https://www.python-httpx.org/)，模板基于 [Jinja2](https://jinja.palletsprojects.com/)

## ⚠️ 免责声明 | Disclaimer

> [!WARNING]
> 本插件会从第三方平台抓取内容并转发到群聊。**是否合规使用由部署者自行判断并承担全部责任。** 内置的敏感词表与 R18 词表只是辅助手段，**不构成内容审核，也不保证覆盖任何一类敏感内容**。

### 一、屏蔽词表不保证完整

插件自带约 150 个政治敏感词和一份 R18 词表，是作者按个人经验整理的，**覆盖面必然有限**。实际内容里存在大量词表无法覆盖的形态：

- 谐音、缩写、拼音首字母、外语、方言、拆字
- 图片、视频、表情包里的文字（词表只检查文本字段）
- 平台自身未打敏感标记的成人内容（R18 判定部分依赖平台标记）
- 新出现的敏感表述，词表更新必然滞后

因此**不能把本插件当作内容审核工具**，更不应据此认为「没被拦截就是安全的」。词表支持自行修改和追加，建议按自己的使用场景维护。

### 二、内容来自第三方

卡片上的标题、正文、作者、配图、评论均抓取自 YouTube、TikTok、X、pixiv 等平台，由第三方用户生成。作者无法控制这些内容，也不对其真实性、准确性、合法性、是否侵犯第三方权利作任何担保。

### 三、账号风险由使用者承担

使用本插件可能导致账号被平台限制、封禁，或导致机器人无法继续使用，包括但不限于：

| 情形 | 可能的后果 |
|---|---|
| 抓取到的内容违反平台服务条款或当地法律法规 | 机器人账号被封禁、群聊被限制 |
| 词表未覆盖的敏感内容被转发到群聊 | 群聊被封、账号被处罚 |
| 高频抓取触发目标平台风控或限流 | X / TikTok 等账号被临时或永久限制 |
| 机器人所在平台对转发内容进行审核处置 | 消息被拦截、账号被降权 |

**因使用本插件造成的账号封禁、限流、内容删除、服务中断、数据丢失，或任何其他直接、间接损失，作者不承担任何责任。**

### 四、部署者的合规义务

部署者应自行确认所在地区法律法规、机器人平台服务条款、目标平台使用条款是否允许此类抓取与转发行为。建议：

- 按自身场景维护词表，不要直接依赖默认词表
- 优先在私密群或小范围使用，避免公开传播抓取内容
- 遵守目标平台的 robots 与 API 条款，控制请求频率
- 涉及成人内容的场景，确保使用者均为成年人
- 定期检查机器人所在平台的规则变化

### 五、接口与可用性

插件依赖第三方公开接口与网页结构，随时可能因对方改版、限流、封锁而失效。作者不保证插件持续可用，也不对因此产生的任何后果负责。

### 六、许可与担保

代码以 MIT 许可发布，意为「按原样提供」（AS IS），**不附带任何明示或暗示的担保**，包括但不限于适销性、特定用途适用性和不侵权担保。详见 [LICENSE](LICENSE)。

## 📜 许可证 | License

本项目基于 [MIT License](LICENSE) 发布，可自由使用、修改和分发，保留版权声明即可。

[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
