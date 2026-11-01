# 通过服务器链接登录 X，自动保存 Cookie

本目录是随插件一起分发的 Docker 服务，提供两件事：远程登录 X 并保存 Cookie（`x-login` 服务），以及供插件调用的浏览器抓取后端（`xbrowser` 服务）。

下文按「已随插件放进 AstrBot 插件目录」的方式写路径，即 `data/plugins/astrbot_plugin_link_preview/x-browser-service`。放在别处时把 `cd` 换成实际目录即可，其余不变。

Cookie 落在哪个目录由 `.env` 的 `ASTRBOT_COOKIE_DIR` 决定，填成实际读取 Cookie 的那个插件的数据目录即可。

部署后，AstrBot 管理员私聊机器人发送 `/xlogin`。机器人返回一个 15 分钟内有效的一次性链接。打开后点击“进入 X 登录窗口”，即可操作服务器上的 Chromium 浏览器，在真实的 X 登录页输入自己的账号、密码并完成验证码/二步验证。聊天软件的链接预览不会消耗登录链接。

浏览器进入 X 首页且取得 `auth_token`、`ct0` 后，服务自动保存 Cookie 并关闭窗口。如果没有自动识别，登录完成后可点击“已完成登录，保存 Cookie”。无需在开发者工具里复制 Cookie。`/xlogin cancel` 关闭窗口并撤销链接。

普通跳转到 X 的链接无法让插件读取你电脑浏览器里的 Cookie。这套服务使用服务器自己的独立浏览器，因此能读取该浏览器登录产生的 Cookie。登录浏览器的临时资料目录在窗口关闭后删除，只有必需 Cookie 写入共享数据目录。

## 部署需求

- Linux 服务器，Docker 和 Docker Compose。
- 一个可配置 HTTPS 反向代理的域名，如 `xlogin.example.com`。只用 IP 的明文 HTTP 不支持公网登录。
- 服务器或登录容器能访问 X；需要时配置 HTTP 代理。
- 足够运行 Chromium 的资源，建议至少预留约 2 GiB 内存。

本服务默认只在宿主机 `127.0.0.1:6080` 监听，通过 HTTPS 反向代理公开。VNC 的 5900 端口仅在容器本机监听，不映射到公网。只有一个登录窗口；再次发送 `/xlogin` 会关闭旧窗口、撤销旧链接。

## 1. 配置共享目录和管理 Token

在服务器的插件目录下操作（安装路径按实际修改）：

```bash
cd /opt/astrbot/data/plugins/astrbot_plugin_link_preview/x-browser-service
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

把生成的随机字符串填入 `.env` 的 `X_LOGIN_SERVICE_TOKEN`。这是登录服务的管理密钥，不是 X 密码或 Cookie。把同一个值填写到 AstrBot 插件配置的 `login_service_token`。

`.env` 示例：

```dotenv
X_LOGIN_SERVICE_TOKEN=你的随机管理Token
X_LOGIN_PUBLIC_URL=https://xlogin.example.com
ASTRBOT_COOKIE_DIR=/opt/astrbot/data/plugin_data/astrbot_plugin_x_search
LOGIN_UID=1000
LOGIN_GID=1000
X_BROWSER_PROXY=
```

`ASTRBOT_COOKIE_DIR` 是**宿主机上**的目录，必须位于 AstrBot 已经持久化挂载的 data 目录内。`LOGIN_UID`、`LOGIN_GID` 请设置成读取 Cookie 的 AstrBot 进程的用户 ID；容器内 AstrBot 使用 root 时可填写 `0`、`0`。普通部署可用 `id 运行AstrBot的用户名` 查看。服务自动保存的文件权限是 `0600`，读取者必须是同一个 UID 或 root。

创建目录并赋予所配置用户写入权限，例如 UID/GID 均为 1000：

```bash
mkdir -p /opt/astrbot/data/plugin_data/astrbot_plugin_x_search
sudo chown 1000:1000 /opt/astrbot/data/plugin_data/astrbot_plugin_x_search
chmod 700 /opt/astrbot/data/plugin_data/astrbot_plugin_x_search
chmod 600 .env
```

如需代理，`X_BROWSER_PROXY` 填登录容器可访问的 HTTP 代理，例如同一 Docker 网络的 `http://clash:7890`。`127.0.0.1` 是登录容器自身。该设置独立于插件用于 Twikit 的 `proxy` 配置，两处都要能访问 X。

## 2. 启动登录服务

```bash
docker compose up -d --build
```

镜像包含 Chromium、虚拟显示和 noVNC。镜像构建需要能下载 Debian 和 Python 依赖。本服务支持 amd64/arm64，使用发行版 Chromium，无需另下载 Playwright 浏览器。

## 3. 配置 HTTPS 反向代理

在 1Panel、宝塔或现有 Nginx 中，为 `xlogin.example.com` 配置有效 TLS 证书，将网站反向代理到 `http://127.0.0.1:6080`，**启用 WebSocket**。

以下片段放在已有的 HTTPS `server` 中；证书和域名按你现有的面板配置：

```nginx
location / {
    proxy_pass http://127.0.0.1:6080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 900s;
    proxy_buffering off;
    access_log off;
}
```

如果反向代理本身也是 Docker 容器，`127.0.0.1` 指反向代理容器；将它加入 `astrbot-x-login` 网络，再把目标改为 `http://x-login:6080`。

`X_LOGIN_PUBLIC_URL` 必须与浏览器访问地址完全一致，包括域名和非默认端口；不要添加路径前缀。服务检查请求来源，域名不匹配会拒绝画面连接或保存操作。

## 4. 配置 AstrBot 插件

普通部署且服务在同一宿主机：

```text
access_mode: web
login_service_url: http://127.0.0.1:6080
login_service_token: 与 .env 中 X_LOGIN_SERVICE_TOKEN 相同
cookies_file: /opt/astrbot/data/plugin_data/astrbot_plugin_x_search/x_cookies.json
```

AstrBot 在 Docker 中，可将它加入登录服务网络（`astrbot` 换成真实容器名）：

```bash
docker network connect astrbot-x-login astrbot
```

然后配置：

```text
access_mode: web
login_service_url: http://x-login:6080
login_service_token: 与 .env 中 X_LOGIN_SERVICE_TOKEN 相同
cookies_file: /AstrBot/data/plugin_data/astrbot_plugin_x_search/x_cookies.json
```

宿主机的共享目录映射给登录服务 `/cookies`，并通过 AstrBot 的原 data 挂载映射给 `/AstrBot/data/plugin_data/astrbot_plugin_x_search`。二者必须是同一个宿主机目录。Docker Compose 用户需把外部 `astrbot-x-login` 网络写进 AstrBot 的 Compose 配置，避免容器重建后丢掉手动加入的网络。

保存配置并重载插件。管理员**私聊**：

```text
/xlogin
```

打开返回链接、完成 X 登录，页面显示“Cookie 已保存在服务器”后，可以直接：

```text
/xsearch 科技
/xpeople 人工智能
/xwrite 科技 || 写一段中文总结
```

无需重启插件：它会在下一次 X 请求读取新 Cookie，并清空旧会话缓存。未来 Cookie 过期时重新 `/xlogin` 即可。

## 5. 浏览器抓取服务（插件 `browser` 模式）

同一个镜像里还带了一个 `scraper.py`，作为插件 `browser` 模式的抓取后端：用真实浏览器加载 X 页面并提取数据，**不受 Twikit 与 X 前端 bundle 不兼容的影响**。

`compose.yaml` 里的 `xbrowser` 服务与 `x-login` 共用镜像和 Cookie 目录，`docker compose up -d` 会一起启动。它只在 `astrbot-x-login` 内部网络监听 6081，不映射公网，接口用同一个 `X_LOGIN_SERVICE_TOKEN` 鉴权。

注意 `xbrowser` 服务**不写 `build:`**：两个服务同时构建同名镜像会冲突，统一由 `x-login` 构建。改代码后重建请用：

```bash
docker compose build x-login && docker compose up -d
```

插件侧配置：

```text
access_mode: browser
browser_service_url: http://xbrowser:6081
browser_service_token: 与 .env 中 X_LOGIN_SERVICE_TOKEN 相同
```

抓取服务还提供 `POST /api/shot`，直接返回真实 X 页面的 PNG 截图（插件 `render_mode: screenshot` 用它替代合成的结果卡片）。截图前会等 `role=progressbar` 的骨架屏消失，避免截到加载中的转圈状态。

浏览器按需启动，空闲 `X_SCRAPER_IDLE` 秒（默认 300）后自动关闭释放内存。抓取服务以 `LOGIN_UID:GID` 运行，因此 Cookie 文件必须能被该用户读取——插件的 `/xcookie` 写入后会自动跟随共享目录属主，手动放文件时注意 `chown` 成同样的 UID。

## 常见问题与验证范围

- `401`：检查管理 Token；链接被使用或过期也会拒绝访问。
- `503`：检查容器 Chromium、虚拟显示、代理及访问 X 的网络。
- 黑屏或画面断开：检查反向代理 WebSocket、域名是否与公开地址一致。
- 保存失败：检查共享目录权限和运行 UID/GID。
- X 要求验证码或二步验证：在真实 X 页面手动完成，服务不自动绕过。
- 登录已保存但搜索失败：网页接口可能拒绝会话或发生变化，检查 Twikit 版本、账户状态和插件代理；不能保证所有服务器 IP 都能使用。

已验证登录服务的本地 HTTP/认证、一次性链接、过期、Cookie 私有权限与原子保存、自动导出以及 WebSocket/VNC 字节转发；没有 Docker 运行环境和真实 X 登录账户，**尚未验证容器构建、完整远程画面和真实 X 登录**。

实现依据：[Playwright 浏览器 Cookie 接口](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-cookies)、[noVNC API](https://github.com/novnc/noVNC/blob/master/docs/API.md)。Cookie 与登录链接都是敏感凭证，不要公开转发。
