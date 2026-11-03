"""国内视频平台：卡片抓取 + 视频下载。

B 站走官方 web 接口（不带 buvid3 会 412），其余平台交给 yt-dlp
（抖音、西瓜、腾讯视频、优酷、爱奇艺、微博、小红书都有对应 extractor）。

下载统一输出 mp4：B 站用 playurl 的 DASH 流，再用 ffmpeg 合并音视频；
其余平台交给 yt-dlp 的 `bv+ba` 格式选择。
"""

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

try:                                    # 作为包的一部分加载（AstrBot 正常路径）
    from .fetchers import FetchError, card, duration, flatten, fmt_time, stat
except ImportError:                     # 单元测试里按顶层模块导入
    from fetchers import FetchError, card, duration, flatten, fmt_time, stat

# 平台 key -> 只在 fetchers.PLATFORMS 里补名字和品牌色，这里只记支持的集合
SUPPORTED = {
    "bilibili", "douyin", "kuaishou", "ixigua",
    "vqq", "youku", "iqiyi", "weibo", "xiaohongshu",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BILI_HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
BILI_API = "https://api.bilibili.com"

BILI_RE = re.compile(r"bilibili\.com/video/(BV[0-9A-Za-z]{10}|av\d+)", re.I)
_buvid = {"v": None, "ts": 0.0}


def bili_target(url):
    """从链接里取出 (BV 号 / av 号, 第几分P)。认不出返回 (None, 1)。"""
    m = BILI_RE.search(str(url or ""))
    if not m:
        return None, 1
    p = re.search(r"[?&]p=(\d+)", str(url))
    return m.group(1), int(p.group(1)) if p else 1


async def resolve_short(client, url):
    """b23.tv / v.douyin.com 这类短链：跟一次跳转拿到真实地址。"""
    try:
        r = await client.get(url, headers={"User-Agent": UA})
        return str(r.url)
    except Exception:
        return url


async def _bili_buvid(client):
    """B 站接口不带 buvid3 会返回 412，先去拿一个（半小时内复用）。"""
    now = time.time()
    if _buvid["v"] and now - _buvid["ts"] < 1800:
        return _buvid["v"]
    try:
        r = await client.get(BILI_API + "/x/frontend/finger/spi", headers=BILI_HEADERS)
        _buvid["v"] = ((r.json() or {}).get("data") or {}).get("b_3")
    except Exception:
        _buvid["v"] = None
    _buvid["ts"] = now
    return _buvid["v"]


async def _bili_get(client, path, params=None):
    headers = dict(BILI_HEADERS)
    b3 = await _bili_buvid(client)
    if b3:
        headers["Cookie"] = f"buvid3={b3}"
    r = await client.get(BILI_API + path, params=params, headers=headers)
    if r.status_code >= 400:
        raise FetchError(f"B 站接口 HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        raise FetchError("B 站接口返回异常") from None
    if data.get("code") != 0:
        raise FetchError(data.get("message") or f"B 站接口错误 {data.get('code')}")
    return data.get("data") or {}


def _https(url):
    return url.replace("http://", "https://", 1) if str(url or "").startswith("http://") else url


async def fetch_bilibili(client, url):
    ident, page = bili_target(url)
    if not ident:
        real = await resolve_short(client, url)
        ident, page = bili_target(real)
        if not ident:
            raise FetchError("没认出这个 B 站链接")
        url = real
    params = {"bvid": ident} if ident.lower().startswith("bv") else {"aid": ident[2:]}
    v = await _bili_get(client, "/x/web-interface/view", params)
    owner = v.get("owner") or {}
    s = v.get("stat") or {}
    pages = v.get("pages") or []
    tags = [t for t in (v.get("tname"), v.get("tname_v2")) if t]
    return card(
        "bilibili", url,
        title=v.get("title"),
        text=flatten(v.get("desc")) or None,
        author={"name": owner.get("name"), "handle": None,
                "avatar": _https(owner.get("face")), "bio": None},
        images=[_https(v["pic"])] if v.get("pic") else [],
        stats=[x for x in (stat("播放", s.get("view")), stat("弹幕", s.get("danmaku")),
                           stat("点赞", s.get("like")), stat("收藏", s.get("favorite"))) if x],
        tags=tags[:3],
        time=fmt_time(v.get("pubdate")),
        video=True,
        duration=duration(v.get("duration")),
        note=f"共 {len(pages)} P" if len(pages) > 1 else None,
    )


async def ytdlp_info(url, timeout=45):
    """用 yt-dlp 取元数据（不下载）。失败抛 FetchError。"""
    cmd = ["yt-dlp", "--dump-single-json", "--skip-download", "--no-playlist",
           "--no-warnings", "--no-progress", "--socket-timeout", "15", url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        raise FetchError("服务器上没装 yt-dlp") from None
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FetchError("解析超时") from None
    if proc.returncode != 0 or not out:
        lines = [x for x in (err or b"").decode("utf-8", "ignore").splitlines() if x.strip()]
        raise FetchError(lines[-1][:80] if lines else "yt-dlp 解析失败")
    try:
        return json.loads(out)
    except ValueError:
        raise FetchError("yt-dlp 返回的不是 JSON") from None


def _upload_date(value):
    s = str(value or "")
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return fmt_time(value)


def card_from_info(platform, url, info):
    thumb = info.get("thumbnail")
    up = info.get("uploader") or info.get("channel") or info.get("creator")
    desc = flatten(info.get("description")) or None
    return card(
        platform, url,
        title=info.get("title"),
        text=desc,
        author={"name": up, "handle": None, "avatar": None, "bio": None},
        images=[thumb] if thumb else [],
        stats=[x for x in (stat("播放", info.get("view_count")),
                           stat("点赞", info.get("like_count")),
                           stat("评论", info.get("comment_count"))) if x],
        tags=[str(t) for t in (info.get("tags") or [])][:3],
        time=_upload_date(info.get("upload_date")),
        video=True,
        duration=duration(info.get("duration")),
    )


async def fetch(client, platform, url):
    """国内平台卡片。B 站走官方接口，其余走 yt-dlp。

    yt-dlp 解析不了（站点改版、没 extractor）就退回通用 OpenGraph，
    总比一条链接什么都不出强。
    """
    if platform == "bilibili":
        return await fetch_bilibili(client, url)
    try:
        info = await ytdlp_info(url)
    except FetchError:
        try:
            from . import fetchers as _f
        except ImportError:
            import fetchers as _f
        c = await _f.fetch_og(client, platform, url)
        c["platform_name"] = _f.PLATFORMS.get(platform, ("网页", ""))[0]
        return c
    return card_from_info(platform, url, info)


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------

async def _stream_to_file(client, urls, path, headers, limit):
    """按顺序试主地址和备用地址。

    B 站 CDN 对不带 Range 的整段请求会返回 567，带上 `Range: bytes=0-` 就正常；
    某个镜像节点挂了还能自动换 backupUrl。
    """
    if isinstance(urls, str):
        urls = [urls]
    headers = dict(headers, Range="bytes=0-")
    last = None
    for url in urls:
        if not url:
            continue
        total = 0
        try:
            async with client.stream("GET", url, headers=headers) as r:
                if r.status_code >= 400:
                    raise FetchError(f"视频流 HTTP {r.status_code}")
                with open(path, "wb") as f:
                    async for chunk in r.aiter_bytes(65536):
                        total += len(chunk)
                        if total > limit:
                            raise FetchError("文件超过大小上限")
                        f.write(chunk)
            if total < 1024:
                raise FetchError("视频流是空的")
            return
        except FetchError as e:
            last = e
            _unlink(path)
        except Exception as e:                      # 网络错误也换下一个地址
            last = FetchError(str(e)[:60])
            _unlink(path)
    raise last or FetchError("视频流下载失败")


async def _ffmpeg_merge(video, audio, out, timeout=180):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
           "-c", "copy", "-movflags", "+faststart", str(out)]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FetchError("音视频合并超时") from None
    if proc.returncode != 0 or not out.exists():
        msg = (err or b"").decode("utf-8", "ignore").strip().splitlines()
        raise FetchError("音视频合并失败" + (f"：{msg[-1][:60]}" if msg else ""))


async def _ffmpeg_copy(src, out, timeout=180):
    """只换容器不重编码：mkv/webm -> mp4。"""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-c", "copy", "-movflags", "+faststart", str(out)]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FetchError("转码超时") from None
    if proc.returncode != 0 or not out.exists():
        raise FetchError("转码失败")


def _unlink(*paths):
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


async def _bili_download(client, url, out_dir, name, max_mb, quality):
    ident, page = bili_target(url)
    if not ident:
        url = await resolve_short(client, url)
        ident, page = bili_target(url)
        if not ident:
            raise FetchError("没认出这个 B 站链接")
    params = {"bvid": ident} if ident.lower().startswith("bv") else {"aid": ident[2:]}
    view = await _bili_get(client, "/x/web-interface/view", params)
    pages = view.get("pages") or []
    cid = pages[min(page, len(pages)) - 1]["cid"] if pages else view.get("cid")
    if not cid:
        raise FetchError("拿不到视频的 cid")

    limit = max_mb * 1024 * 1024
    last = None
    for qn in [q for q in (64, 32, 16) if q <= quality] or [16]:
        try:
            data = await _bili_get(client, "/x/player/playurl",
                                   {"bvid": ident, "cid": cid, "qn": qn, "fnval": 16, "fourk": 1})
        except FetchError as e:
            last = e
            continue
        dash = data.get("dash") or {}
        videos = dash.get("video") or []
        audios = dash.get("audio") or []
        if not videos or not audios:
            last = FetchError("没有可用的视频流（可能需要登录）")
            continue
        video = max(videos, key=lambda x: (x.get("height") or 0, x.get("bandwidth") or 0))
        audio = max(audios, key=lambda x: x.get("bandwidth") or 0)
        seconds = view.get("duration") or 0
        if (video.get("bandwidth") or 0) * seconds / 8 > limit:
            last = FetchError("文件超过大小上限")
            continue

        vpath = out_dir / f"{name}-v.m4s"
        apath = out_dir / f"{name}-a.m4s"
        try:
            await _stream_to_file(client, [video.get("baseUrl")] + (video.get("backupUrl") or []),
                                  vpath, BILI_HEADERS, limit)
            await _stream_to_file(client, [audio.get("baseUrl")] + (audio.get("backupUrl") or []),
                                  apath, BILI_HEADERS, limit)
        except FetchError as e:
            last = e
            _unlink(vpath, apath)
            continue
        out = out_dir / f"{name}.mp4"
        await _ffmpeg_merge(vpath, apath, out)
        _unlink(vpath, apath)
        return out
    raise last or FetchError("B 站下载失败")


async def _ytdlp_download(url, out_dir, name, max_mb, quality, timeout=300):
    target = out_dir / f"{name}.%(ext)s"
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings", "--no-progress",
           "-f", f"bv*[height<={quality}]+ba/b[height<={quality}]/b",
           "--merge-output-format", "mp4",
           "--max-filesize", f"{max_mb}M", "--socket-timeout", "20",
           "-o", str(target), url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        raise FetchError("服务器上没装 yt-dlp") from None
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise FetchError("下载超时") from None

    files = [p for p in out_dir.glob(f"{name}.*") if p.suffix.lower() in (".mp4", ".mkv", ".webm")]
    if files:
        path = max(files, key=lambda p: p.stat().st_size)
        if path.stat().st_size > max_mb * 1024 * 1024:
            _unlink(path)
            raise FetchError("文件超过大小上限")
        if path.suffix.lower() != ".mp4":
            merged = out_dir / f"{name}.mp4"
            await _ffmpeg_copy(path, merged)          # 兜底：把容器转成 mp4
            _unlink(path)
            return merged
        return path

    lines = [x for x in (err or b"").decode("utf-8", "ignore").splitlines() if x.strip()]
    raise FetchError(lines[-1][:80] if lines else "下载失败")


async def download(client, platform, url, out_dir, max_mb=80, quality=720):
    """下载成 mp4，返回文件路径。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = hashlib.md5(f"{url}|{time.time()}".encode()).hexdigest()[:12]
    if platform == "bilibili":
        return await _bili_download(client, url, out_dir, name, max_mb, quality)
    return await _ytdlp_download(url, out_dir, name, max_mb, quality)
