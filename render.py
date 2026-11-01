"""把卡片字典画成图片：图片先下载内联成 data URI，再用本机 Chromium 截图。"""

import asyncio
import base64
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import jinja2

try:                      # 插件里跑用 AstrBot 的 logger；单独跑脚本时退回标准库
    from astrbot.api import logger
except Exception:         # pragma: no cover - 只在本机调试时走到
    import logging

    logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).parent / "templates" / "card.html"

# 徽章里的小图标（只用常见字体都有的字符）
ICONS = {
    "x": "X", "youtube": "▶", "reddit": "r", "github": "G", "bluesky": "B", "pixiv": "P",
    "steam": "S", "wikipedia": "W", "wikisource": "文", "tiktok": "♪", "spotify": "♫", "vimeo": "V",
    "soundcloud": "S", "instagram": "I", "threads": "@", "twitch": "T", "facebook": "f", "web": "↗",
    "dailymotion": "d", "niconico": "N",
}

_env = jinja2.Environment(autoescape=True)


def _clip(text, n):
    if not text:
        return text
    text = str(text).strip()
    return text if len(text) <= n else text[:n].rstrip() + "…"


async def _data_uri(client, url, referer=None, max_bytes=6 * 1024 * 1024):
    if not url:
        return None
    try:
        headers = {"Referer": referer} if referer else {}
        r = await client.get(url, headers=headers)
        ctype = r.headers.get("content-type", "").split(";")[0].strip()
        if r.status_code != 200 or not ctype.startswith("image/") or len(r.content) > max_bytes:
            return None
        return f"data:{ctype};base64," + base64.b64encode(r.content).decode()
    except Exception:
        return None


async def prepare(client, card, text_length=420, show_images=True, comments_mode=False):
    """下载图片、截断文字，返回可以直接套模板的卡片。

    comments_mode=True 是 /评论 指令用的评论卡：正文缩短、不放图片，评论放宽。
    """
    c = dict(card)
    c["comments_mode"] = comments_mode
    if comments_mode:
        show_images = False
        text_length = min(text_length, 120)
    ref = c.get("referer")
    avatar = (c.get("author") or {}).get("avatar")
    imgs = c.get("images") if show_images else []
    results = await asyncio.gather(
        _data_uri(client, avatar, ref),
        *[_data_uri(client, u, ref) for u in (imgs or [])[:4]],
    )
    if c.get("author"):
        c["author"] = dict(c["author"], avatar=results[0])
    c["images"] = [u for u in results[1:] if u]
    c["title"] = _clip(c.get("title"), 140)
    c["text"] = _clip(c.get("text"), text_length)
    c["comments"] = [dict(x, text=_clip(x.get("text"), 300 if comments_mode else 140))
                     for x in c.get("comments") or [] if x.get("text")]
    if c.get("quote"):
        c["quote"] = dict(c["quote"], text=_clip(c["quote"].get("text"), 200))
    host = urlsplit(c["url"]).hostname or ""
    c["domain"] = host.removeprefix("www.")
    short = unquote(c["url"].split("://", 1)[-1])
    c["short_url"] = short if len(short) <= 64 else short[:63] + "…"
    c["icon"] = ICONS.get(c["platform"], "↗")
    if c.get("sensitive") and c.get("images"):
        c["blur"] = True
        c["note"] = c.get("note") or "平台标记的敏感内容"
    return c


ARTICLE = Path(__file__).parent / "templates" / "article.html"


async def prepare_article(client, article):
    """维基全文：首图转成 data URI，补上显示用的域名和短链接。"""
    a = dict(article)
    a["image"] = await _data_uri(client, a.get("image"))
    a["domain"] = urlsplit(a["url"]).hostname or "wikipedia.org"
    short = unquote(a["url"].split("://", 1)[-1])
    a["short_url"] = short if len(short) <= 70 else short[:69] + "…"
    return a


def build_article_html(article, blocks, no, total, hidden=0, theme="dark"):
    tpl = _env.from_string(ARTICLE.read_text(encoding="utf-8"))
    return tpl.render(a=article, blocks=blocks, no=no, total=total, hidden=hidden,
                      theme="light" if theme == "light" else "dark")


def build_html(card, theme="dark"):
    tpl = _env.from_string(TEMPLATE.read_text(encoding="utf-8"))
    return tpl.render(c=card, theme="light" if theme == "light" else "dark")


# 常见系统浏览器的安装位置：没装 Playwright 自带 Chromium 时按顺序试
SYSTEM_BROWSERS = {
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "linux": [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/microsoft-edge",
    ],
}

LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--disable-extensions"]


def launch_options(channel="auto", path=""):
    """按优先级列出浏览器启动方式。

    指定路径 > 指定通道（chrome/msedge/chromium）> 自动找系统浏览器 > Playwright 自带的。
    这样机器上只要有 Chrome/Edge 就能渲染，不必装 Docker，也不用跑 playwright install-deps。
    """
    out = []
    path = str(path or "").strip()
    if path:
        out.append({"executable_path": path})
    ch = str(channel or "auto").strip().lower()
    if ch in ("chrome", "msedge", "chromium"):
        out.append({"channel": ch})
    elif ch == "auto":
        for p in SYSTEM_BROWSERS.get(sys.platform, SYSTEM_BROWSERS["linux"]):
            if os.path.exists(p):
                out.append({"executable_path": p})
    out.append({})        # 兜底：Playwright 自带的 Chromium
    return out


class Renderer:
    """复用同一个无头浏览器；同时最多渲染两张。"""

    def __init__(self, channel="auto", path=""):
        self._pw = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(2)
        self._options = launch_options(channel, path)
        self._current = None

    async def _ensure(self):
        async with self._lock:
            if self._browser and self._browser.is_connected():
                return self._browser
            from playwright.async_api import async_playwright

            if self._pw is None:
                self._pw = await async_playwright().start()
            # 上次成功的那个优先重试，失败再按顺序降级
            order = ([self._current] if self._current else []) + [
                o for o in self._options if o != self._current
            ]
            last = None
            for opt in order:
                try:
                    self._browser = await self._pw.chromium.launch(args=LAUNCH_ARGS, **opt)
                    if opt != self._current:
                        logger.info(f"[LinkPreview] 浏览器已启动：{opt or 'Playwright 自带 Chromium'}")
                    self._current = opt
                    return self._browser
                except Exception as e:
                    last = e
                    logger.debug(f"[LinkPreview] 启动方式不可用 {opt}：{e}")
            raise RuntimeError(f"没有可用的浏览器：{last}")

    async def render(self, html, out_path, timeout=25):
        browser = await self._ensure()
        async with self._sem:
            page = await browser.new_page(viewport={"width": 680, "height": 600}, device_scale_factor=2)
            try:
                await page.set_content(html, wait_until="load", timeout=timeout * 1000)
                await page.evaluate("document.fonts.ready")
                el = await page.query_selector("#card")
                await el.screenshot(path=str(out_path), type="jpeg", quality=90, timeout=timeout * 1000)
            finally:
                await page.close()
        return out_path

    async def close(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._browser = self._pw = None
