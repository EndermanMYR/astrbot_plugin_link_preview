"""一次性登录入口、受认证的 VNC 通道与 Cookie 导出；不提供凭证下载接口。"""

import asyncio
import contextlib
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web

COOKIE_NAME = "x_login_session"


def extract_cookies(values):
    cookies = {}
    for item in values:
        if str(item.get("domain", "")).lstrip(".") in {
            "x.com",
            "twitter.com",
        } and item.get("name") in {"auth_token", "ct0"}:
            cookies[item["name"]] = item.get("value")
    if not all(
        isinstance(cookies.get(key), str) and cookies[key].strip()
        for key in ("auth_token", "ct0")
    ):
        raise ValueError("尚未取得完整登录 Cookie")
    return cookies


def save_cookies(path, cookies):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 临时文件默认 0600，同一目录内原子替换，不留下半写入的 Cookie 文件。
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as output:
        temporary = Path(output.name)
        try:
            json.dump(cookies, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class RemoteBrowser:
    def __init__(self, executable="/usr/bin/chromium", proxy=""):
        self.executable = executable
        self.proxy = proxy
        self.engine = None
        self.context = None
        self.profile = None

    async def open(self):
        from playwright.async_api import async_playwright

        self.engine = await async_playwright().start()
        self.profile = tempfile.TemporaryDirectory(prefix="x-login-browser-")
        options = {
            "headless": False,
            "executable_path": self.executable,
            "viewport": {"width": 1240, "height": 800},
            "args": [
                "--window-size=1280,900",
                "--window-position=0,0",
                "--disable-dev-shm-usage",
            ],
        }
        if self.proxy:
            options["proxy"] = {"server": self.proxy}
        self.context = await self.engine.chromium.launch_persistent_context(
            self.profile.name, **options
        )
        page = (
            self.context.pages[0]
            if self.context.pages
            else await self.context.new_page()
        )
        await page.goto(
            "https://x.com/i/flow/login", wait_until="domcontentloaded", timeout=60000
        )

    async def cookies(self):
        return await self.context.cookies(["https://x.com/", "https://twitter.com/"])

    def is_home(self):
        for page in self.context.pages:
            url = urlsplit(page.url)
            if (
                url.hostname in {"x.com", "twitter.com"}
                and url.path.rstrip("/") == "/home"
            ):
                return True
        return False

    async def close(self):
        try:
            if self.context:
                await self.context.close()
        finally:
            try:
                if self.engine:
                    await self.engine.stop()
            finally:
                if self.profile:
                    self.profile.cleanup()
                self.context = self.engine = self.profile = None


@dataclass
class Session:
    ticket: str
    browser_token: str
    expires: float
    redeemed: bool = False
    status: str = "pending"


class LoginService:
    def __init__(
        self,
        admin_token,
        public_url,
        cookie_path,
        runtime_factory=None,
        ttl=900,
        novnc_dir="/opt/novnc",
        vnc_port=5900,
    ):
        if len(admin_token) < 32 or admin_token.startswith("replace-with-"):
            raise ValueError("登录服务管理 Token 至少 32 个字符")
        url = urlsplit(public_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
        ):
            raise ValueError("公开地址需为完整的域名根地址")
        if url.scheme != "https" and url.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("公开登录地址必须使用 HTTPS")
        self.admin_token = admin_token
        self.public_url = public_url.rstrip("/")
        self.secure_cookie = url.scheme == "https"
        self.cookie_path = cookie_path
        self.runtime_factory = runtime_factory or RemoteBrowser
        self.ttl = max(30, min(1800, ttl))
        self.novnc_dir = Path(novnc_dir)
        self.vnc_port = vnc_port
        self.session = None
        self.runtime = None
        self.watcher = None
        self.ws = None
        self.lock = asyncio.Lock()

    def app(self):
        app = web.Application(client_max_size=4096, middlewares=[self.headers])
        app.router.add_get("/health", self.health)
        app.router.add_post("/api/session", self.new_session)
        app.router.add_post("/api/cancel", self.cancel_session)
        app.router.add_get("/login/{ticket}", self.redeem)
        app.router.add_post("/redeem/{ticket}", self.activate)
        app.router.add_get("/entry/{name}", self.entry_asset)
        app.router.add_get("/", self.portal)
        app.router.add_get("/status", self.status)
        app.router.add_post("/finish", self.finish)
        app.router.add_get("/ws", self.websocket)
        app.router.add_get("/novnc/{path:.*}", self.assets)
        app.on_cleanup.append(self.cleanup)
        return app

    @web.middleware
    async def headers(self, request, handler):
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.Response(
                status=exc.status, text=exc.text, headers=exc.headers
            )
        if not isinstance(response, web.WebSocketResponse):
            response.headers.update(
                {
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; frame-ancestors 'none'",
                }
            )
        return response

    def admin(self, request):
        supplied = request.headers.get("Authorization", "")
        if not secrets.compare_digest(
            supplied.encode(), ("Bearer " + self.admin_token).encode()
        ):
            raise web.HTTPUnauthorized(text="未授权")

    def authorized(self, request, running=False):
        session = self.session
        token = request.cookies.get(COOKIE_NAME, "")
        if (
            not session
            or not session.redeemed
            or time.monotonic() >= session.expires
            or not secrets.compare_digest(
                token.encode(), session.browser_token.encode()
            )
        ):
            raise web.HTTPUnauthorized(text="登录链接或会话已失效，请重新发送 /xlogin")
        if running and session.status != "pending":
            raise web.HTTPGone(text="登录窗口已关闭")
        return session

    def origin(self, request):
        if request.headers.get("Origin") != self.public_url:
            raise web.HTTPForbidden(text="来源不匹配")

    async def health(self, request):
        return web.json_response({"ok": True})

    async def _close_runtime(self):
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
        runtime, self.runtime = self.runtime, None
        if runtime is not None:
            with contextlib.suppress(Exception):
                await runtime.close()

    async def _stop(self):
        if self.watcher:
            self.watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.watcher
            self.watcher = None
        await self._close_runtime()

    async def new_session(self, request):
        self.admin(request)
        async with self.lock:
            await self._stop()
            self.session = None
            self.runtime = self.runtime_factory()
            try:
                await asyncio.wait_for(self.runtime.open(), timeout=75)
            except Exception:  # noqa: BLE001 - external browser boundary, never expose credential details
                await self._close_runtime()
                raise web.HTTPServiceUnavailable(
                    text="远程浏览器启动失败，请检查服务网络和浏览器运行环境。"
                ) from None
            session = Session(
                secrets.token_urlsafe(32),
                secrets.token_urlsafe(32),
                time.monotonic() + self.ttl,
            )
            self.session = session
            self.watcher = asyncio.create_task(self.watch(session))
            return web.json_response(
                {
                    "login_url": self.public_url + "/login/" + session.ticket,
                    "expires_in": self.ttl,
                }
            )

    async def cancel_session(self, request):
        self.admin(request)
        async with self.lock:
            await self._stop()
            self.session = None
        return web.json_response({"ok": True})

    async def redeem(self, request):
        session = self.session
        supplied = request.match_info["ticket"]
        if (
            not session
            or session.redeemed
            or session.status != "pending"
            or time.monotonic() >= session.expires
            or not secrets.compare_digest(supplied.encode(), session.ticket.encode())
        ):
            raise web.HTTPGone(text="一次性链接已使用或过期，请重新发送 /xlogin")
        # GET 只展示入口；聊天软件的链接预览不会消耗一次性凭证。
        return web.Response(
            text=(Path(__file__).parent / "welcome.html").read_text(encoding="utf-8"),
            content_type="text/html",
        )

    async def activate(self, request):
        self.origin(request)
        session = self.session
        supplied = request.match_info["ticket"]
        if (
            not session
            or session.redeemed
            or session.status != "pending"
            or time.monotonic() >= session.expires
            or not secrets.compare_digest(supplied.encode(), session.ticket.encode())
        ):
            raise web.HTTPGone(text="一次性链接已使用或过期，请重新发送 /xlogin")
        session.redeemed = True
        response = web.json_response({"ok": True})
        response.set_cookie(
            COOKIE_NAME,
            session.browser_token,
            max_age=self.ttl,
            httponly=True,
            secure=self.secure_cookie,
            samesite="Strict",
        )
        return response

    async def entry_asset(self, request):
        name = request.match_info["name"]
        if name not in {"portal.css", "start.js"}:
            raise web.HTTPNotFound()
        return web.FileResponse(Path(__file__).parent / name)

    async def portal(self, request):
        self.authorized(request)
        return web.Response(
            text=(Path(__file__).parent / "portal.html").read_text(encoding="utf-8"),
            content_type="text/html",
        )

    async def assets(self, request):
        self.authorized(request)
        name = request.match_info["path"]
        if name in {"portal.js", "portal.css"}:
            return web.FileResponse(Path(__file__).parent / name)
        root = self.novnc_dir.resolve()
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def status(self, request):
        session = self.authorized(request)
        return web.json_response(
            {
                "status": session.status,
                "remaining_seconds": max(0, int(session.expires - time.monotonic())),
            }
        )

    async def _save(self, session):
        cookies = extract_cookies(await self.runtime.cookies())
        await asyncio.to_thread(save_cookies, self.cookie_path, cookies)
        session.status = "saved"
        await self._close_runtime()

    async def finish(self, request):
        session = self.authorized(request, running=True)
        self.origin(request)
        async with self.lock:
            if session is not self.session or session.status != "pending":
                raise web.HTTPGone(text="会话已结束")
            try:
                await self._save(session)
            except ValueError:
                raise web.HTTPBadRequest(
                    text="尚未取得完整登录 Cookie，请在 X 窗口完成登录后再试。"
                ) from None
            except OSError:
                raise web.HTTPInternalServerError(
                    text="Cookie 保存失败，请检查共享目录写入权限。"
                ) from None
        return web.json_response({"ok": True, "status": "saved"})

    async def watch(self, session):
        try:
            while session is self.session and session.status == "pending":
                await asyncio.sleep(2)
                async with self.lock:
                    if session is not self.session or session.status != "pending":
                        return
                    if time.monotonic() >= session.expires:
                        session.status = "expired"
                        await self._close_runtime()
                        return
                    if self.runtime.is_home():
                        try:
                            await self._save(session)
                            return
                        except ValueError:
                            continue
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - external browser boundary, fail closed
            session.status = "failed"
            await self._close_runtime()

    async def websocket(self, request):
        self.authorized(request, running=True)
        self.origin(request)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", self.vnc_port)
        except OSError:
            raise web.HTTPServiceUnavailable(text="远程画面服务不可用") from None
        if self.ws is not None:
            await self.ws.close()
        ws = web.WebSocketResponse(
            protocols=("binary",), heartbeat=20, max_msg_size=1048576
        )
        await ws.prepare(request)
        self.ws = ws

        async def desktop_to_browser():
            while data := await reader.read(65536):
                await ws.send_bytes(data)
            await ws.close()

        stream = asyncio.create_task(desktop_to_browser())
        try:
            async for message in ws:
                if message.type == WSMsgType.BINARY:
                    writer.write(message.data)
                    await writer.drain()
                elif message.type in {WSMsgType.TEXT, WSMsgType.ERROR}:
                    break
        finally:
            stream.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionError):
                await stream
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()
            if self.ws is ws:
                self.ws = None
            await ws.close()
        return ws

    async def cleanup(self, app):
        await self._stop()


def main():
    service = LoginService(
        os.environ.get("X_LOGIN_SERVICE_TOKEN", ""),
        os.environ.get("X_LOGIN_PUBLIC_URL", ""),
        os.environ.get("X_COOKIE_FILE", "/cookies/x_cookies.json"),
        runtime_factory=lambda: RemoteBrowser(
            proxy=os.environ.get("X_BROWSER_PROXY", "")
        ),
    )
    web.run_app(service.app(), host="0.0.0.0", port=6080, access_log=None)


if __name__ == "__main__":
    main()
