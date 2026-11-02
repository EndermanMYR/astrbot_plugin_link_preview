# 抓取后端（X）

给插件提供 X 的搜索、用户、帖子详情接口。**不含登录门户**——Cookie 由插件配置里的 `x_cookie` 直接写入，不需要在服务器上开浏览器登录。

## 部署

```bash
cd x-browser-service
cp .env.example .env
# 编辑 .env：填 Token，确认 Cookie 目录
docker compose up -d
```

**默认本地构建，不联网拉镜像。** 第一次约 10 分钟，主要花在装 chromium 上；之后层都在本机缓存里，改 `scraper.py` 重建只要几秒。国内网络卡在 PyPI 时在 `.env` 里加一行：

```dotenv
PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```

不想等第一次构建的话，可以用 GitHub Actions 预构建好的镜像（公共可拉，不需要登录）：

```dotenv
# .env
XBROWSER_IMAGE=ghcr.io/endermanmyr/astrbot-xbrowser:latest
```

然后 `docker compose up -d`，几秒钟起好。注意 `ghcr.io` 在部分网络环境下不可达，连不上就删掉这行、用默认的本地构建。镜像每次改动后由 [workflow](../.github/workflows/docker.yml) 自动构建。

`.env` 示例：

```dotenv
X_LOGIN_SERVICE_TOKEN=你的随机Token（32 字符以上）
ASTRBOT_COOKIE_DIR=/opt/astrbot/data/plugin_data/astrbot_plugin_link_preview
LOGIN_UID=1000
LOGIN_GID=1000
X_SCRAPER_IDLE=1800
```

- `X_LOGIN_SERVICE_TOKEN` 就是插件配置里的 `x_browser_token`，两边必须一致。
- `ASTRBOT_COOKIE_DIR` 是**宿主机**目录，插件会把 `x_cookie` 写到这里，容器挂载成 `/cookies`。
- `LOGIN_UID` / `LOGIN_GID` 是容器运行用户，需与写文件的进程一致（容器内 AstrBot 是 root 时填 `0`、`0`）。
- `X_SCRAPER_IDLE` 空闲多少秒关掉浏览器，默认 1800。调小省内存，调大减少冷启动（冷启动多花 8~10 秒）。
- `XBROWSER_IMAGE` 想换镜像源时改这个；`PIP_INDEX` 只在本地构建时生效。

## 不用 Docker：裸机 / systemd

它就是个 aiohttp 服务，容器只是省事。裸机跑只要三样东西：Python 3.10+、`aiohttp` + `playwright`、一个 Chromium。

```bash
# 1. 依赖
sudo apt install -y python3-venv chromium fonts-noto-cjk
python3 -m venv /opt/xbrowser/venv
/opt/xbrowser/venv/bin/pip install aiohttp playwright

# 没有系统 chromium 的机器（macOS / Windows / 精简发行版）：
/opt/xbrowser/venv/bin/python -m playwright install chromium
# 脚本会自动回退到 Playwright 自带的那份；也可用 X_CHROMIUM=/path/to/chrome 指定

# 2. 放代码和配置
sudo mkdir -p /opt/xbrowser/cookies
sudo cp scraper.py /opt/xbrowser/
sudo cp .env.example /opt/xbrowser/.env      # 填 Token 和 Cookie 目录

# 3. 交给 systemd
sudo useradd -r -s /usr/sbin/nologin xbrowser
sudo chown -R xbrowser:xbrowser /opt/xbrowser
sudo cp deploy/xbrowser.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now xbrowser
```

然后插件里填 `x_browser_url = http://127.0.0.1:6081`（不是容器名 `xbrowser`），Token 用 `.env` 里那个。

裸机和容器只差两点：

| 项 | 容器 | 裸机 |
|---|---|---|
| 监听地址 | `0.0.0.0:6081`（容器间互访） | 建议 `127.0.0.1:6081`，`X_SCRAPER_HOST` 控制 |
| 浏览器 | 镜像里装的 `/usr/bin/chromium` | 系统 chromium，或 `playwright install chromium` 后自动回退 |

可用环境变量：

| 变量 | 说明 |
|---|---|
| `X_LOGIN_SERVICE_TOKEN` | 必填，插件里的 `x_browser_token` |
| `X_COOKIE_FILE` | Cookie 文件路径，默认 `/cookies/x_cookies.json` |
| `X_SCRAPER_PORT` / `X_SCRAPER_HOST` | 监听端口 / 地址，默认 `6081` / `0.0.0.0` |
| `X_SCRAPER_IDLE` | 空闲多少秒关掉浏览器，默认 1800 |
| `X_CHROMIUM` | 浏览器可执行文件路径，不存在时回退到 Playwright 自带的 |

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
