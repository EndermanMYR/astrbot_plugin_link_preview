"""用服务器浏览器读取 X 页面并提取结构化数据，供插件 browser 模式调用。

与 twikit 不同，这里让真实浏览器加载并执行 X 自己的前端，因此不受
X 前端 bundle 结构变化的影响。仅执行读取操作。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from aiohttp import web
from playwright.async_api import async_playwright

COOKIE_FILE = os.environ.get("X_COOKIE_FILE", "/cookies/x_cookies.json")
TOKEN = os.environ.get("X_LOGIN_SERVICE_TOKEN", "")
PORT = int(os.environ.get("X_SCRAPER_PORT", "6081"))
IDLE_SECONDS = int(os.environ.get("X_SCRAPER_IDLE", "600"))
# 空闲回收的巡检间隔（秒）。
REAP_INTERVAL = 60
NAV_TIMEOUT = int(os.environ.get("X_SCRAPER_TIMEOUT", "45000"))
# 首次冷启动时 X 前端渲染较慢，先等关键元素出现，再补一次重试。
READY_TIMEOUT = int(os.environ.get("X_SCRAPER_READY_TIMEOUT", "25000"))
# 骨架屏（role=progressbar）最多再等这么久，避免截到转圈状态。
SPINNER_TIMEOUT = int(os.environ.get("X_SCRAPER_SPINNER_TIMEOUT", "15000"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BLOCK_MARKERS = (
    "Something went wrong",
    "出错了",
    "Try reloading",
    "Rate limit exceeded",
    "rate limit exceeded",
    "操作过于频繁",
)

# 真实页面截图的目标；值由插件侧校验后传入。
SHOT_TARGETS = {
    "search": lambda v: f"https://x.com/search?q={quote(v)}&src=typed_query&f=live",
    "search_top": lambda v: f"https://x.com/search?q={quote(v)}&src=typed_query&f=top",
    "users": lambda v: f"https://x.com/search?q={quote(v)}&src=typed_query&f=user",
    "profile": lambda v: f"https://x.com/{v}",
    "post": lambda v: f"https://x.com/i/status/{v}",
}
SHOT_READY = {
    "search": 'article[data-testid="tweet"]',
    "search_top": 'article[data-testid="tweet"]',
    "users": '[data-testid="UserCell"]',
    "profile": '[data-testid="UserName"]',
    "post": 'article[data-testid="tweet"]',
}

# 截图只保留内容列：隐藏左侧导航整栏（含登录账号）、右侧栏（搜索过滤/
# 推荐关注）和右下角悬浮按钮（Grok / 聊天）。账号不随图片外发，
# 这些导航和推荐对读帖也没有意义。用 CSS 隐藏而非裁剪，避免切掉正文。
HIDE_CSS = """
header[role="banner"] { display: none !important; }
[data-testid="sidebarColumn"] { display: none !important; }
[data-testid="GrokDrawer"] { display: none !important; }
[data-testid="GrokDrawerHeader"] { display: none !important; }
[data-testid="chat-drawer-root"] { display: none !important; }
[data-testid="SideNav_AccountSwitcher_Button"] { visibility: hidden !important; }
main[role="main"], [data-testid="primaryColumn"] {
  width: 100% !important;
  max-width: 100% !important;
  flex: 1 1 auto !important;
}
"""

# 量出内容列的实际位置，截图按它裁剪，彻底避免右侧留白。
COLUMN_BOX_JS = """
() => {
  const el = document.querySelector('[data-testid="primaryColumn"]')
    || document.querySelector('main[role="main"]');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.x, width: r.width };
}
"""

# 内容列里最后一块内容的下沿（文档坐标）。列表页用不到，单帖页用。
CONTENT_BOTTOM_JS = """
() => {
  const col = document.querySelector('[data-testid="primaryColumn"]');
  if (!col) return null;
  let bottom = 0;
  for (const kid of col.children) {
    const r = kid.getBoundingClientRect();
    if (r.height > 0) bottom = Math.max(bottom, r.bottom + window.scrollY);
  }
  return bottom ? Math.round(bottom) : null;
}
"""

# 单帖页首条帖子的下沿（文档坐标）。帖子页会自动滚到帖子位置，
# 先回到顶部再量，才能把图片裁成正好一条帖子的高度。
FIRST_TWEET_BOTTOM_JS = """
() => {
  const col = document.querySelector('[data-testid="primaryColumn"]');
  const art = col && col.querySelector('article[data-testid="tweet"]');
  if (!art) return null;
  const r = art.getBoundingClientRect();
  return Math.round(r.bottom + window.scrollY);
}
"""

# ---------------------------------------------------------------- 页面内提取
# 注意：以下均为 JS 源码，用 Python 原始字符串保存，不要转义反斜杠。

NUM_HELPER = r"""
  const num = (s) => {
    if (!s) return 0;
    const m = String(s).replace(/,/g, '').match(/([\d.]+)\s*([万萬KkMm]?)/);
    if (!m) return 0;
    let n = parseFloat(m[1]);
    if (!isFinite(n)) return 0;
    const u = m[2].toLowerCase();
    if (u === '万' || u === '萬') n *= 10000;
    else if (u === 'k') n *= 1000;
    else if (u === 'm') n *= 1000000;
    return Math.round(n);
  };
  const HANDLE_RE = /^\/[A-Za-z0-9_]{1,15}$/;
  const handleFrom = (root) => {
    const av = root.querySelector('[data-testid^="UserAvatar-Container-"]');
    if (av) {
      const h = (av.getAttribute('data-testid') || '')
        .replace('UserAvatar-Container-', '');
      if (h && h !== 'unknown') return h;
    }
    for (const a of root.querySelectorAll('a[href]')) {
      const h = a.getAttribute('href') || '';
      if (HANDLE_RE.test(h)) return h.slice(1);
    }
    const m = (root.innerText || '').match(/@([A-Za-z0-9_]{1,15})/);
    return m ? m[1] : '';
  };
  const nameFrom = (root, handle) => {
    for (const a of root.querySelectorAll('a[href]')) {
      if ((a.getAttribute('href') || '') !== '/' + handle) continue;
      const sp = a.querySelector('span');
      const v = ((sp ? sp.innerText : a.innerText) || '').trim();
      if (v && !v.startsWith('@')) return v;
    }
    for (const line of (root.innerText || '').split('\n')) {
      const t = line.trim();
      if (!t || t.startsWith('@') || t === handle) continue;
      if (/关注者|粉丝|Followers|正在关注|Following|帖子|Posts/.test(t)) continue;
      return t;
    }
    return '';
  };
"""

TWEET_JS = (
    r"""
() => {"""
    + NUM_HELPER
    + r"""
  const metric = (art, testid) => {
    const host = art.querySelector('[data-testid="' + testid + '"]');
    if (!host) return 0;
    const inner = host.querySelector('[aria-label]');
    const label = host.getAttribute('aria-label')
      || (inner ? inner.getAttribute('aria-label') : '')
      || host.innerText || '';
    return num(label);
  };
  const handleOf = (art) => {
    const box = art.querySelector('[data-testid="User-Name"]');
    if (box) {
      for (const a of box.querySelectorAll('a[href]')) {
        const h = a.getAttribute('href') || '';
        if (HANDLE_RE.test(h)) return h.slice(1);
      }
    }
    return handleFrom(art);
  };
  const nameOf = (art) => {
    const box = art.querySelector('[data-testid="User-Name"]');
    if (!box) return '';
    for (const a of box.querySelectorAll('a[href]')) {
      const h = a.getAttribute('href') || '';
      if (HANDLE_RE.test(h)) {
        const sp = a.querySelector('span');
        const v = ((sp ? sp.innerText : a.innerText) || '').trim();
        if (v && !v.startsWith('@')) return v;
      }
    }
    const line = (box.innerText || '').split('\n')[0] || '';
    return line.replace(/^@/, '').trim();
  };
  const out = [];
  for (const art of document.querySelectorAll('article[data-testid="tweet"]')) {
    const timeEl = art.querySelector('time');
    let href = '';
    if (timeEl) {
      const a = timeEl.closest('a[href]');
      if (a) href = a.getAttribute('href') || '';
    }
    if (!href) {
      for (const a of art.querySelectorAll('a[href*="/status/"]')) {
        const h = a.getAttribute('href') || '';
        if (/\/status\/\d+$/.test(h)) { href = h; break; }
      }
    }
    const idm = href.match(/\/status\/(\d+)/);
    const textEl = art.querySelector('[data-testid="tweetText"]');
    const body = art.innerText || '';
    const ctx = art.querySelector('[data-testid="socialContext"]');
    out.push({
      id: idm ? idm[1] : '',
      handle: handleOf(art),
      name: nameOf(art),
      text: textEl ? (textEl.innerText || '') : '',
      created_at: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
      like_count: metric(art, 'like'),
      retweet_count: metric(art, 'retweet'),
      reply_count: metric(art, 'reply'),
      is_retweet: !!(ctx && /转推|Reposted|已转推/.test(ctx.innerText || '')),
      sensitive: /可能包含敏感内容|may contain sensitive content|敏感内容/.test(body),
      url: href ? 'https://x.com' + href : '',
    });
  }
  return out;
}
"""
)

USER_CELL_JS = (
    r"""
() => {"""
    + NUM_HELPER
    + r"""
  const out = [];
  for (const cell of document.querySelectorAll('[data-testid="UserCell"]')) {
    const handle = handleFrom(cell);
    const desc = cell.querySelector('[data-testid="UserDescription"]');
    let description = desc ? (desc.innerText || '').trim() : '';
    if (!description) {
      // 该版本的用户搜索卡片没有 UserDescription，取最长的一段正文行兜底。
      let best = '';
      for (const line of (cell.innerText || '').split('\n')) {
        const t = line.trim();
        if (!t || t.length <= best.length) continue;
        if (t.startsWith('@') || t === handle) continue;
        if (/关注者|粉丝|Followers|正在关注|Following/.test(t)) continue;
        if (t === nameFrom(cell, handle)) continue;
        best = t;
      }
      description = best;
    }
    const fm = (cell.innerText || '').match(
      /([\d.,]+\s*[万萬KkMm]?)\s*(关注者|粉丝|Followers)/i
    );
    out.push({
      handle: handle,
      name: nameFrom(cell, handle),
      description: description,
      followers_count: fm ? num(fm[1]) : 0,
      url: handle ? 'https://x.com/' + handle : '',
    });
  }
  return out;
}
"""
)

PROFILE_JS = (
    r"""
() => {"""
    + NUM_HELPER
    + r"""
  const q = (sel) => document.querySelector(sel);
  const nameEl = q('[data-testid="UserName"]');
  if (!nameEl) return {exists: false};
  const lines = (nameEl.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
  let name = '', handle = '';
  for (const line of lines) {
    if (line.startsWith('@') && !handle) handle = line.slice(1);
    else if (!name && line && !/^\d/.test(line)) name = line;
  }
  if (!handle) handle = location.pathname.replace(/^\//, '').split('/')[0] || '';

  let followers = 0, following = 0, tweets = 0;
  for (const a of document.querySelectorAll('a[href]')) {
    const h = a.getAttribute('href') || '';
    const t = a.innerText || '';
    if (/\/(verified_)?followers$/.test(h) && /关注者|粉丝|Followers/i.test(t)) {
      followers = num(t);
    } else if (/\/following$/.test(h) && /正在关注|Following/i.test(t)) {
      following = num(t);
    }
  }
  const body = document.body.innerText || '';
  const tm = body.match(/([\d.,]+\s*[万萬KkMm]?)\s*(帖子|Posts)/i);
  if (tm) tweets = num(tm[1]);
  const jm = body.match(/(\d{4}年\d{1,2}月|\w+ \d{4})\s*(加入|Joined)/);
  const joined = jm ? jm[1] : '';

  // 个人简介没有稳定的 data-testid，从 UserName 向上取几层，
  // 只扫描到「加入/关注数」之前，避免把下方时间线的推文当成简介。
  let node = nameEl;
  for (let i = 0; i < 3 && node && node.parentElement; i++) node = node.parentElement;
  let description = '';
  for (const line of ((node ? node.innerText : '') || '').split('\n')) {
    const t = line.trim();
    if (!t) continue;
    if (/加入|Joined|关注者|粉丝|Followers|正在关注|Following|帖子|Posts/.test(t)) break;
    if (t.startsWith('@') || t === name || t === handle) continue;
    if (/翻译|显示原文|Translate|Show original/.test(t)) continue;
    if (/和你关注的另外|关注了此账号|followed by|Followed by/i.test(t)) continue;
    if (/^\d[\d.,]*\s*$/.test(t)) continue;
    if (t.length > description.length) description = t;
  }
  return {
    handle: handle,
    name: name,
    description: description,
    location: '',
    created_at: joined,
    followers_count: followers,
    following_count: following,
    tweet_count: tweets,
    protected: /这些帖子仅对已批准的关注者可见|These posts are protected/.test(body),
    exists: true,
  };
}
"""
)


def _iso(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except (TypeError, ValueError):
        return str(value)


def _load_cookies() -> list[dict]:
    raw = json.loads(open(COOKIE_FILE, encoding="utf-8").read())
    out = []
    for name in ("auth_token", "ct0"):
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("Cookie 文件缺少 auth_token 或 ct0。")
        out.append(
            {
                "name": name,
                "value": value.strip(),
                "domain": ".x.com",
                "path": "/",
                "secure": True,
            }
        )
    return out


def _timings(ready_timeout_ms, settle_ms, default_settle):
    """把插件传来的等待参数换算成秒；缺省时用服务端默认值。"""
    ready = (
        READY_TIMEOUT
        if ready_timeout_ms is None
        else max(3, min(int(ready_timeout_ms) // 1000, 90))
    )
    settle = (
        default_settle
        if settle_ms is None
        else max(200, min(int(settle_ms), 8000))
    )
    return ready, settle


# 浏览器被回收/崩溃时 Playwright 抛出的典型报错。这类错误不是页面内容问题，
# 重建浏览器再跑一次通常就能成功，不该直接甩给用户。
BROWSER_DEAD_HINTS = (
    "has been closed",
    "target closed",
    "has disconnected",
    "browser closed",
    "crashed",
)


def _browser_dead(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(hint in text for hint in BROWSER_DEAD_HINTS)


class Browser:
    """常驻浏览器上下文；串行处理请求，空闲一段时间后自动关闭释放内存。"""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._ctx = None
        self._lock = asyncio.Lock()
        self._last_used = 0.0
        self._reaper = None
        self._cookie_stamp = None

    @staticmethod
    def _cookie_stamp_now():
        try:
            return os.path.getmtime(COOKIE_FILE)
        except OSError:
            return None

    async def _ensure(self):
        stamp = self._cookie_stamp_now()
        if self._ctx is not None and stamp != self._cookie_stamp:
            # Cookie 文件被换过（例如用了 /xcookie），旧会话立即作废。
            await self._close()
        if self._ctx is not None:
            return self._ctx
        if self._pw is None:
            self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            executable_path=os.environ.get("X_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        self._ctx = await self._browser.new_context(
            locale="zh-CN",
            viewport={"width": 1280, "height": 1000},
            user_agent=USER_AGENT,
        )
        await self._ctx.add_cookies(_load_cookies())
        self._cookie_stamp = stamp
        if self._reaper is None:
            self._reaper = asyncio.create_task(self._reap())
        return self._ctx

    async def _reap(self):
        while True:
            await asyncio.sleep(REAP_INTERVAL)
            if not self._ctx or not IDLE_SECONDS:
                continue
            if time.monotonic() - self._last_used <= IDLE_SECONDS:
                continue
            # 必须持锁再关：否则可能在请求进行中把浏览器/页面关掉，让正在执行的
            # Playwright 调用抛 "Target page, context or browser has been closed"。
            async with self._lock:
                # 拿到锁后重新确认一次，避免刚被新请求刷新过。
                if time.monotonic() - self._last_used > IDLE_SECONDS:
                    try:
                        await self._close()
                    except Exception:  # noqa: BLE001 - 后台回收不应影响服务
                        pass

    async def _close(self):
        if self._ctx is not None:
            await self._ctx.close()
        if self._browser is not None:
            await self._browser.close()
        self._ctx = self._browser = None

    async def close(self):
        async with self._lock:
            await self._close()

    async def _fetch_once(
        self,
        url: str,
        wait_ms: int,
        extract_js: str,
        ready: str = "",
        ready_timeout_ms=None,
        settle_ms=None,
    ):
        ready_timeout, settle = _timings(ready_timeout_ms, settle_ms, wait_ms)
        async with self._lock:
            # 立刻打上「占用中」时间戳：_last_used 若只在结束时更新，空闲回收器会在
            # 长操作（如 /xmore 多次滚动）期间误判为空闲并关掉浏览器。
            self._last_used = time.monotonic()
            ctx = await self._ensure()
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
                if ready:
                    try:
                        await page.wait_for_selector(ready, timeout=ready_timeout * 1000)
                    except Exception:  # noqa: BLE001 - 超时就按现有 DOM 提取
                        pass
                await page.wait_for_timeout(settle)
                body = await page.inner_text("body")
                for marker in BLOCK_MARKERS:
                    if marker in body:
                        raise RuntimeError(
                            "X 页面提示访问异常，可能是该服务器 IP 被限流，请稍后重试。"
                        )
                data = await page.evaluate(extract_js)
                missing = (
                    not data
                    if isinstance(data, list)
                    else data.get("exists") is False
                )
                if missing and ready:
                    # 冷启动首屏可能还没渲染出结果，再等一轮。
                    await page.wait_for_timeout(settle * 2)
                    data = await page.evaluate(extract_js)
                return data
            finally:
                await page.close()
                self._last_used = time.monotonic()

    async def _shot_once(
        self,
        url: str,
        ready: str,
        height: int,
        full_page: bool,
        ready_timeout_ms=None,
        settle_ms=None,
        scroll: int = 0,
        fit: bool = False,
    ):
        """截取真实 X 页面，返回 (图片字节, content-type)。

        scroll 表示「先向下翻几屏再截当前屏」，用于 /xmore 翻页；
        始终只输出一屏，不拼长图。full_page 才输出整页长图（JPEG）。
        """
        ready_timeout, settle = _timings(ready_timeout_ms, settle_ms, 1200)
        steps = max(0, min(int(scroll or 0), 12))
        async with self._lock:
            # 立刻打上「占用中」时间戳：_last_used 若只在结束时更新，空闲回收器会在
            # 长操作（如 /xmore 多次滚动）期间误判为空闲并关掉浏览器。
            self._last_used = time.monotonic()
            ctx = await self._ensure()
            page = await ctx.new_page()
            try:
                await page.set_viewport_size({"width": 1280, "height": height})
                await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
                await page.add_style_tag(content=HIDE_CSS)
                if ready:
                    try:
                        await page.wait_for_selector(ready, timeout=ready_timeout * 1000)
                    except Exception:  # noqa: BLE001 - 超时就截当前画面
                        pass
                # X 首屏常用 role=progressbar 的骨架屏；等它消失再截图，避免截到转圈。
                try:
                    await page.wait_for_function(
                        "() => !document.querySelector('[role=\"progressbar\"]')",
                        timeout=SPINNER_TIMEOUT,
                    )
                except Exception:  # noqa: BLE001 - 等不到也照样截
                    pass
                await page.wait_for_timeout(settle)
                for _ in range(steps):
                    await page.mouse.wheel(0, height)
                    await page.wait_for_timeout(2200)
                body = await page.inner_text("body")
                for marker in BLOCK_MARKERS:
                    if marker in body:
                        raise RuntimeError(
                            "X 页面提示访问异常，可能是该服务器 IP 被限流，请稍后重试。"
                        )
                clip = None
                box = await page.evaluate(COLUMN_BOX_JS)
                if box and box.get("width", 0) >= 200:
                    left = max(0, int(box["x"]))
                    width = min(int(box["width"]), 1280 - left)
                    clip = {"x": left, "y": 0, "width": width, "height": height}
                long_page = bool(full_page)
                if long_page:
                    if clip:
                        clip = {**clip, "height": 100000}
                    return (
                        await page.screenshot(
                            full_page=True,
                            type="jpeg",
                            quality=82,
                            animations="disabled",
                            clip=clip,
                        ),
                        "image/jpeg",
                    )
                # 短页（单帖）把高度贴合到实际内容，避免下面一大片白。
                if clip and fit:
                    await page.evaluate("() => window.scrollTo(0, 0)")
                    await page.wait_for_timeout(700)
                    bottom = await page.evaluate(FIRST_TWEET_BOTTOM_JS)
                    if bottom:
                        clip = {
                            **clip,
                            "height": max(400, min(height, int(bottom) + 12)),
                        }
                return (
                    await page.screenshot(
                        full_page=False, type="png", animations="disabled", clip=clip
                    ),
                    "image/png",
                )
            finally:
                await page.close()
                self._last_used = time.monotonic()

    async def _retry(self, fn, args, kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - 需按错误类型判断能否重试
            if not _browser_dead(exc):
                raise
            # 浏览器可能刚被空闲回收，或被系统 OOM 杀掉。丢弃旧实例重建一次再试，
            # 避免把偶发的浏览器崩溃直接抛给用户。
            async with self._lock:
                await self._close()
            return await fn(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        return await self._retry(self._fetch_once, args, kwargs)

    async def shot(self, *args, **kwargs):
        return await self._retry(self._shot_once, args, kwargs)


BROWSER = Browser()


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _post_item(raw):
    handle = raw.get("handle") or ""
    return {
        "id": raw.get("id", ""),
        "text": raw.get("text", ""),
        "author": {
            "id": "",
            "username": handle,
            "name": raw.get("name", ""),
            "description": "",
            "location": "",
            "created_at": "",
            "verified": False,
            "protected": False,
            "metrics": {},
            "url": f"https://x.com/{handle}" if handle else "",
        },
        "created_at": _iso(raw.get("created_at", "")),
        "metrics": {
            "like_count": raw.get("like_count", 0),
            "retweet_count": raw.get("retweet_count", 0),
            "reply_count": raw.get("reply_count", 0),
        },
        "sensitive": bool(raw.get("sensitive")),
        "is_retweet": bool(raw.get("is_retweet")),
        "url": raw.get("url", ""),
    }


def _user_item(raw, related=None):
    handle = raw.get("handle") or ""
    item = {
        "id": "",
        "username": handle,
        "name": raw.get("name", ""),
        "description": raw.get("description", ""),
        "location": raw.get("location", ""),
        "created_at": raw.get("created_at", ""),
        "verified": False,
        "protected": bool(raw.get("protected", False)),
        "sensitive": False,
        "metrics": {
            "followers_count": raw.get("followers_count", 0),
            "following_count": raw.get("following_count", 0),
            "tweet_count": raw.get("tweet_count", 0),
        },
        "url": raw.get("url") or (f"https://x.com/{handle}" if handle else ""),
    }
    if related:
        item["related_post_url"] = related
    return item


# ---------------------------------------------------------------- HTTP 接口


def _auth_ok(request) -> bool:
    header = request.headers.get("Authorization", "")
    return bool(TOKEN) and header == "Bearer " + TOKEN


@web.middleware
async def guard(request, handler):
    if request.path == "/health":
        return await handler(request)
    if not _auth_ok(request):
        return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


async def health(request):
    return web.json_response({"ok": True, "browser": BROWSER._ctx is not None})


async def api_cookies(request):
    """手动写入 Cookie。Browser 会按文件 mtime 自动重载，不用重启。"""
    body = await request.json()
    auth = str(body.get("auth_token", "")).strip()
    ct0 = str(body.get("ct0", "")).strip()
    if not auth or not ct0:
        return web.json_response({"error": "auth_token 和 ct0 都不能为空"}, status=400)
    try:
        os.makedirs(os.path.dirname(COOKIE_FILE) or ".", exist_ok=True)
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump({"auth_token": auth, "ct0": ct0}, f, indent=2)
        os.chmod(COOKIE_FILE, 0o600)
    except OSError as e:
        return web.json_response({"error": f"写入失败：{e}"}, status=500)
    return web.json_response({"ok": True})


async def api_search(request):
    body = await request.json()
    query = str(body.get("query", "")).strip()
    count = max(1, min(int(body.get("count") or 5), 20))
    kind = "users" if body.get("mode") == "users" else "posts"
    top = str(body.get("tab", "")).lower() == "top"
    if not query or len(query) > 512:
        return web.json_response({"error": "搜索词需为 1–512 个字符。"}, status=400)
    suffix = "f=user" if kind == "users" else ("f=top" if top else "f=live")
    url = f"https://x.com/search?q={quote(query)}&src=typed_query&{suffix}"
    ready_ms, settle_ms = body.get("ready_timeout_ms"), body.get("settle_ms")
    if kind == "users":
        raw = await BROWSER.fetch(
            url,
            8000,
            USER_CELL_JS,
            '[data-testid="UserCell"]',
            ready_ms,
            settle_ms,
        )
        items = [_user_item(u) for u in raw if u.get("handle")][:count]
        source = "X 浏览器用户搜索"
    else:
        raw = await BROWSER.fetch(
            url,
            8000,
            TWEET_JS,
            'article[data-testid="tweet"]',
            ready_ms,
            settle_ms,
        )
        items = [_post_item(t) for t in raw if t.get("id")][:count]
        source = "X 浏览器热门帖子搜索" if top else "X 浏览器最新帖子搜索"
    return web.json_response({"source": source, "items": items, "fetched_at": _stamp()})


async def api_user(request):
    body = await request.json()
    handle = re.sub(r"^@", "", str(body.get("handle", "")).strip())
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        return web.json_response({"error": "用户名格式不正确。"}, status=400)
    raw = await BROWSER.fetch(
        f"https://x.com/{handle}",
        7000,
        PROFILE_JS,
        '[data-testid="UserName"]',
        body.get("ready_timeout_ms"),
        body.get("settle_ms"),
    )
    if not raw.get("exists"):
        return web.json_response({"error": "未找到该用户。"}, status=404)
    raw["handle"] = handle
    return web.json_response(
        {
            "source": "X 浏览器用户资料",
            "items": [_user_item(raw)],
            "fetched_at": _stamp(),
        }
    )


async def api_user_posts(request):
    body = await request.json()
    handle = re.sub(r"^@", "", str(body.get("handle", "")).strip())
    count = max(1, min(int(body.get("count") or 5), 20))
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        return web.json_response({"error": "用户名格式不正确。"}, status=400)
    raw = await BROWSER.fetch(
        f"https://x.com/{handle}",
        8000,
        TWEET_JS,
        'article[data-testid="tweet"]',
        body.get("ready_timeout_ms"),
        body.get("settle_ms"),
    )
    items = [_post_item(t) for t in raw if t.get("id")][: count * 2]
    items = [i for i in items if not i["is_retweet"]][:count]
    return web.json_response(
        {
            "source": "X 浏览器用户最近帖子（排除转发）",
            "items": items,
            "fetched_at": _stamp(),
        }
    )


async def api_post(request):
    body = await request.json()
    value = str(body.get("value", "")).strip()
    m = re.search(r"/status/(\d{1,19})", value) or re.fullmatch(r"(\d{1,19})", value)
    if not m:
        return web.json_response({"error": "请提供帖子链接或数字 ID。"}, status=400)
    raw = await BROWSER.fetch(
        f"https://x.com/i/status/{m.group(1)}",
        8000,
        TWEET_JS,
        'article[data-testid="tweet"]',
        body.get("ready_timeout_ms"),
        body.get("settle_ms"),
    )
    items = [_post_item(t) for t in raw if t.get("id") == m.group(1)]
    if not items:
        return web.json_response({"error": "未找到该帖子。"}, status=404)
    return web.json_response(
        {"source": "X 浏览器帖子详情", "items": items, "fetched_at": _stamp()}
    )


async def api_shot(request):
    """截取真实 X 页面，直接返回图片字节。"""
    body = await request.json()
    target = str(body.get("target", "")).strip()
    value = str(body.get("value", "")).strip()
    height = max(600, min(int(body.get("height") or 1400), 3000))
    full_page = bool(body.get("full_page"))
    scroll = max(0, min(int(body.get("scroll") or 0), 8))
    if target not in SHOT_TARGETS or not value:
        return web.json_response({"error": "截图目标或参数不正确。"}, status=400)
    data, content_type = await BROWSER.shot(
        SHOT_TARGETS[target](value),
        SHOT_READY[target],
        height,
        full_page,
        body.get("ready_timeout_ms"),
        body.get("settle_ms"),
        scroll,
        # 单帖页内容很短，裁剪到帖子实际高度，避免大片留白。
        fit=target == "post" and not full_page and scroll == 0,
    )
    return web.Response(body=data, content_type=content_type)


@web.middleware
async def errors(request, handler):
    try:
        return await handler(request)
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        return web.json_response({"error": str(exc)[:300]}, status=502)


async def on_cleanup(app):
    await BROWSER.close()


def make_app():
    app = web.Application(middlewares=[errors, guard])
    app.router.add_get("/health", health)
    app.router.add_post("/api/cookies", api_cookies)
    app.router.add_post("/api/search", api_search)
    app.router.add_post("/api/user", api_user)
    app.router.add_post("/api/user_posts", api_user_posts)
    app.router.add_post("/api/post", api_post)
    app.router.add_post("/api/shot", api_shot)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=PORT, access_log=None)
