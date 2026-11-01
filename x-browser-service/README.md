# 抓取后端（X）

给插件提供 X 的搜索、用户、帖子详情接口。**不含登录门户**——Cookie 由插件配置里的 `x_cookie` 直接写入，不需要在服务器上开浏览器登录。

## 部署

```bash
cd x-browser-service
cp .env.example .env
# 编辑 .env：填 Token，确认 Cookie 目录
docker compose up -d
```

`.env` 示例：

```dotenv
X_LOGIN_SERVICE_TOKEN=你的随机Token（32 字符以上）
ASTRBOT_COOKIE_DIR=/opt/astrbot/data/plugin_data/astrbot_plugin_link_preview
LOGIN_UID=1000
LOGIN_GID=1000
X_SCRAPER_IDLE=300
```

- `X_LOGIN_SERVICE_TOKEN` 就是插件配置里的 `x_browser_token`，两边必须一致。
- `ASTRBOT_COOKIE_DIR` 是**宿主机**目录，插件会把 `x_cookie` 写到这里，容器挂载成 `/cookies`。
- `LOGIN_UID` / `LOGIN_GID` 是容器运行用户，需与写文件的进程一致（容器内 AstrBot 是 root 时填 `0`、`0`）。
- `X_SCRAPER_IDLE` 空闲多少秒关掉浏览器，默认 300。

## 接口

所有接口都要 `Authorization: Bearer <Token>`，只有 `/health` 不需要。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 存活检查 |
| POST | `/api/cookies` | 写入 `auth_token` / `ct0`，写文件后自动重载 |
| POST | `/api/search` | 帖子/用户搜索 |
| POST | `/api/user` | 用户资料 |
| POST | `/api/user_posts` | 用户最近帖子 |
| POST | `/api/post` | 单条帖子详情 |
| POST | `/api/shot` | 页面截图 |

## Cookie 从哪来

**在插件里填**，不用碰这个目录：

1. 电脑浏览器登录 x.com
2. F12 → Application → Cookies → `https://x.com`
3. 复制 `auth_token`（40 位）和 `ct0`（160 位）
4. 拼成 `auth_token=xxx; ct0=yyy` 填进插件的 `x_cookie`

插件加载时会把这段 Cookie POST 到 `/api/cookies`，服务写文件后按 mtime 自动重载，不用重启。

## 说明

- 容器里只有 Chromium，没有 VNC / Xvfb，内存占用小。
- Cookie 失效的表现是评论变空，重新复制一次即可。
- 不要用浏览器自动化反复登录 X——容易触发风控封 IP，手填 Cookie 更稳。
