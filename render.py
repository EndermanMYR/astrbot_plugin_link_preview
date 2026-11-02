"""把卡片字典变成 HTML，交给 AstrBot 的文转图服务出图，再裁掉多余留白。"""

import asyncio
import base64
from pathlib import Path
from urllib.parse import unquote, urlsplit

import jinja2

from astrbot.api import logger

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


def build_html(card, theme="dark", t2i=True):
    """渲染成 HTML 字符串。t2i=True 时套用文转图的版式（铺满 800 宽视口）。"""
    tpl = _env.from_string(TEMPLATE.read_text(encoding="utf-8"))
    return tpl.render(c=card, theme="light" if theme == "light" else "dark", t2i=t2i)


# ---------------------------------------------------------------------------
# 文转图（AstrBot 的 html_render）：远端服务固定 800 宽视口、DPR 1，
# 忽略 device_scale_factor，高度会随内容延伸但不会小于 720。
# 所以模板里让卡片铺满 800 宽（body.t2i），出图后再裁掉多余留白。

def t2i_options():
    """交给 AstrBot 文转图服务的截图参数。"""
    return {"type": "jpeg", "quality": 92, "full_page": True}


def crop_image(path, pad=8, threshold=10):
    """裁掉四周与背景色相同的留白。

    远端视口高度固定 720，矮卡片下方会留一大片纯背景色；左右也可能有边距。
    这里按「与左上角背景色的差异」求包围盒，再留一点阴影边距。
    """
    from PIL import Image, ImageChops

    try:
        im = Image.open(path).convert("RGB")
    except (OSError, ValueError):
        return path
    w, h = im.size
    if w < 8 or h < 8:
        return path

    bg = im.getpixel((2, 2))
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg)).convert("L")
    mask = diff.point(lambda v: 255 if v > threshold else 0)
    box = mask.getbbox()
    if not box:
        return path

    left = max(0, box[0] - pad)
    top = max(0, box[1] - pad)
    right = min(w, box[2] + pad)
    bottom = min(h, box[3] + pad)
    if (left, top, right, bottom) == (0, 0, w, h):
        return path

    im.crop((left, top, right, bottom)).save(path, "JPEG", quality=92)
    return path
