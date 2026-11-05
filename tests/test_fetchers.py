"""fetchers 的纯函数测试：不联网、不需要 AstrBot。"""

import asyncio
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests._stub import install  # noqa: E402

install()

import fetchers  # noqa: E402

with open(os.path.join(ROOT, "_conf_schema.json"), encoding="utf-8") as f:
    PLATFORM_ITEMS = json.load(f)["platforms"]["items"]

# 用户在配置里能开关的全部平台（threads/twitch/facebook 走 og 兜底，不在 LINK_PATTERNS 里）
ALL_ON = {k: True for k in PLATFORM_ITEMS}


class TestFindLinks(unittest.TestCase):
    def test_x_link(self):
        got = fetchers.find_links("看看 https://x.com/jack/status/20 这个", ALL_ON)
        self.assertEqual(got, [("x", "https://x.com/jack/status/20")])

    def test_twitter_alias_and_vx(self):
        for url in ("https://twitter.com/jack/status/20",
                    "https://vxtwitter.com/jack/status/20",
                    "https://x.com/i/status/20"):
            got = fetchers.find_links(url, ALL_ON)
            self.assertEqual(got[0][0], "x", url)

    def test_youtube_watch_and_short(self):
        got = fetchers.find_links("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ALL_ON)
        self.assertEqual(got[0][0], "youtube")
        got = fetchers.find_links("https://youtu.be/dQw4w9WgXcQ", ALL_ON)
        self.assertEqual(got[0][0], "youtube")

    def test_github_repo_and_issue(self):
        got = fetchers.find_links("https://github.com/EndermanMYR/astrbot_plugin_link_preview", ALL_ON)
        self.assertEqual(got[0][0], "github")
        got = fetchers.find_links("https://github.com/o/r/issues/12", ALL_ON)
        self.assertEqual(got[0][0], "github")

    def test_github_reserved_path_ignored(self):
        # /issues 是保留路径，不该当成仓库
        self.assertEqual(fetchers.find_links("https://github.com/issues", ALL_ON), [])

    def test_steam_wikipedia_pixiv(self):
        cases = {
            "https://store.steampowered.com/app/730": "steam",
            "https://zh.wikipedia.org/wiki/猫": "wikipedia",
            "https://www.pixiv.net/artworks/1": "pixiv",
            "https://bsky.app/profile/a.bsky.social/post/abc123": "bluesky",
        }
        for url, want in cases.items():
            got = fetchers.find_links(url, ALL_ON)
            self.assertEqual(got[0][0], want, url)

    def test_og_sites_map_to_real_names(self):
        got = fetchers.find_links("https://www.threads.net/@someone/post/xyz", ALL_ON)
        self.assertEqual(got[0][0], "threads")
        got = fetchers.find_links("https://www.twitch.tv/somestreamer", ALL_ON)
        self.assertEqual(got[0][0], "twitch")

    def test_limit_respected(self):
        text = ("https://youtu.be/dQw4w9WgXcQ "
                "https://store.steampowered.com/app/730 "
                "https://www.pixiv.net/artworks/1 "
                "https://zh.wikipedia.org/wiki/猫")
        self.assertEqual(len(fetchers.find_links(text, ALL_ON, limit=2)), 2)
        self.assertEqual(len(fetchers.find_links(text, ALL_ON, limit=10)), 4)

    def test_disabled_platform_filtered(self):
        enabled = dict(ALL_ON)
        enabled["youtube"] = False
        self.assertEqual(fetchers.find_links("https://youtu.be/dQw4w9WgXcQ", enabled), [])

    def test_trailing_punctuation_stripped(self):
        got = fetchers.find_links("链接在这 https://youtu.be/dQw4w9WgXcQ。", ALL_ON)
        self.assertEqual(got[0][1], "https://youtu.be/dQw4w9WgXcQ")

    def test_duplicate_url_only_once(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        self.assertEqual(len(fetchers.find_links(f"{url} 和 {url}", ALL_ON)), 1)

    def test_empty_text(self):
        self.assertEqual(fetchers.find_links("", ALL_ON), [])
        self.assertEqual(fetchers.find_links(None, ALL_ON), [])


class TestWebFallback(unittest.TestCase):
    """没被任何平台匹配到的链接按通用网页预览，但要挡掉内网和直链文件。"""

    def test_unknown_site_falls_back_to_web(self):
        got = fetchers.find_links("https://example.com/post/1", ALL_ON)
        self.assertEqual(got, [("web", "https://example.com/post/1")])

    def test_known_platform_still_wins(self):
        self.assertEqual(fetchers.find_links("https://github.com/o/r", ALL_ON)[0][0], "github")

    def test_private_hosts_skipped(self):
        for url in ("http://localhost:8080/x", "http://192.168.1.1/admin", "http://10.0.0.5/",
                    "http://172.16.3.4/", "http://127.0.0.1:6199/", "http://nas.local/",
                    "http://intranet/"):
            self.assertEqual(fetchers.find_links(url, ALL_ON), [], url)

    def test_direct_files_skipped(self):
        for url in ("https://example.com/a.jpg", "https://example.com/doc.pdf",
                    "https://example.com/pack.zip", "https://example.com/app.apk"):
            self.assertEqual(fetchers.find_links(url, ALL_ON), [], url)

    def test_blocklist_covers_subdomains(self):
        blocked = ["bilibili.com"]
        for url in ("https://www.bilibili.com/video/BV1xx", "https://live.bilibili.com/123"):
            self.assertEqual(fetchers.find_links(url, ALL_ON, 3, blocked), [], url)
        self.assertTrue(fetchers.find_links("https://example.com/x", ALL_ON, 3, blocked))

    def test_blocked_link_does_not_use_up_limit(self):
        text = "http://192.168.1.1/ https://example.com/x"
        self.assertEqual(fetchers.find_links(text, ALL_ON, 1),
                         [("web", "https://example.com/x")])

    def test_web_can_be_disabled(self):
        off = dict(ALL_ON, web=False)
        self.assertEqual(fetchers.find_links("https://example.com/x", off), [])

    def test_is_previewable_web(self):
        self.assertTrue(fetchers.is_previewable_web("https://example.com/a/b"))
        self.assertFalse(fetchers.is_previewable_web("ftp://example.com/a"))
        self.assertFalse(fetchers.is_previewable_web("https://example/a"))
        self.assertFalse(fetchers.is_previewable_web(""))


class TestBareUrls(unittest.TestCase):
    """群里常直接发 www.bilibili.com 这种没协议的域名。"""

    def test_bare_domain(self):
        self.assertEqual(fetchers.find_links("www.bilibili.com", ALL_ON),
                         [("web", "https://www.bilibili.com")])

    def test_bare_domain_with_path(self):
        self.assertEqual(fetchers.find_links("看www.bilibili.com/video/BV1xx 这个", ALL_ON),
                         [("web", "https://www.bilibili.com/video/BV1xx")])

    def test_bare_domain_keeps_platform(self):
        self.assertEqual(fetchers.find_links("github.com/o/r", ALL_ON)[0][0], "github")
        self.assertEqual(fetchers.find_links("x.com/jack/status/20", ALL_ON)[0][0], "x")

    def test_no_false_positive(self):
        for text in ("版本 1.2.3 发布了", "文件 file.txt", "a@b.com", "e.g. this", "随便聊聊"):
            self.assertEqual(fetchers.find_links(text, ALL_ON), [], text)

    def test_scheme_url_not_counted_twice(self):
        self.assertEqual(fetchers.find_links("https://example.com/x", ALL_ON),
                         [("web", "https://example.com/x")])

    def test_chinese_domain(self):
        for text, want in (("中文.中国", "https://中文.中国"),
                           ("中国政府.政务", "https://中国政府.政务"),
                           ("中文域名.cn", "https://中文域名.cn"),
                           ("百度.中国/搜索", "https://百度.中国/搜索")):
            self.assertEqual(fetchers.find_links(text, ALL_ON), [("web", want)], text)

    def test_chinese_domain_needs_boundary(self):
        """中文域名夹在中文句子里没法分词，宁可不认。"""
        for text in ("看中文.中国这个", "我买了个中文.中国域名"):
            self.assertEqual(fetchers.find_links(text, ALL_ON), [], text)
        # 有分隔就认
        self.assertEqual(fetchers.find_links("推荐 中文.中国", ALL_ON),
                         [("web", "https://中文.中国")])
        self.assertEqual(fetchers.find_links("中文.中国，很好用", ALL_ON),
                         [("web", "https://中文.中国")])

    def test_chinese_text_does_not_break_ascii_domain(self):
        self.assertEqual(fetchers.find_links("看www.bilibili.com这个", ALL_ON),
                         [("web", "https://www.bilibili.com")])

    def test_punycode_domain(self):
        self.assertEqual(fetchers.find_links("xn--fiq228c.xn--fiqs8s", ALL_ON),
                         [("web", "https://xn--fiq228c.xn--fiqs8s")])

    def test_extra_tlds(self):
        """内置列表之外的顶级域，可以在配置里补充。"""
        self.assertEqual(fetchers.find_links("example.zip", ALL_ON), [])
        self.assertEqual(fetchers.find_links("example.zip", ALL_ON, 3, None, ["zip"]),
                         [("web", "https://example.zip")])
        self.assertEqual(fetchers.find_links("测试.测试域", ALL_ON, 3, None, ["测试域"]),
                         [("web", "https://测试.测试域")])

    def test_extra_tlds_normalized(self):
        self.assertEqual(fetchers.normalize_tlds([".ZIP", "zip", " 中国 ", "", None]),
                         ("zip", "中国"))

    def test_extra_tlds_do_not_leak(self):
        """正则按额外顶级域缓存，两套配置不能互相污染。"""
        self.assertTrue(fetchers.find_links("example.zip", ALL_ON, 3, None, ["zip"]))
        self.assertEqual(fetchers.find_links("example.zip", ALL_ON), [])
        self.assertEqual(fetchers.find_links("example.mov", ALL_ON), [])

    def test_candidate_order(self):
        self.assertEqual(fetchers.candidate_urls("先 https://a.com/1 再 b.com/2"),
                         ["https://a.com/1", "https://b.com/2"])


class TestCnVideo(unittest.TestCase):
    """国内视频平台：链接解析、卡片字段、平台表一致性。"""

    def test_bili_target(self):
        import cnvideo
        self.assertEqual(cnvideo.bili_target("https://www.bilibili.com/video/BV119Hg6aE87"),
                         ("BV119Hg6aE87", 1))
        self.assertEqual(cnvideo.bili_target("https://m.bilibili.com/video/av12345"),
                         ("av12345", 1))
        self.assertEqual(cnvideo.bili_target("https://www.bilibili.com/video/BV119Hg6aE87?p=3"),
                         ("BV119Hg6aE87", 3))
        self.assertEqual(cnvideo.bili_target("https://b23.tv/iVrYSRK"), (None, 1))

    def test_platform_tables_match(self):
        import cnvideo
        self.assertEqual(set(cnvideo.SUPPORTED), set(fetchers.CN_VIDEO))
        for key in cnvideo.SUPPORTED:
            self.assertIn(key, fetchers.PLATFORMS, f"{key} 没在 PLATFORMS 里")

    def test_card_from_info(self):
        import cnvideo
        info = {
            "title": "测试视频", "uploader": "某UP", "duration": 93,
            "view_count": 12345, "like_count": 678, "comment_count": 9,
            "thumbnail": "https://example.com/t.jpg", "upload_date": "20260102",
            "description": "简介第一行\n第二行", "tags": ["a", "b", "c", "d"],
        }
        c = cnvideo.card_from_info("douyin", "https://v.douyin.com/x", info)
        self.assertEqual(c["title"], "测试视频")
        self.assertEqual(c["author"]["name"], "某UP")
        self.assertEqual(c["images"], ["https://example.com/t.jpg"])
        self.assertEqual(c["duration"], "1:33")
        self.assertEqual(c["time"], "2026-01-02")
        self.assertEqual(c["stats"][0], ["播放", "1.2万"])
        self.assertEqual(len(c["tags"]), 3)
        self.assertTrue(c["video"])

    def test_upload_date_passthrough(self):
        import cnvideo
        self.assertEqual(cnvideo._upload_date("20260102"), "2026-01-02")
        self.assertEqual(cnvideo._upload_date(None), None)

    def test_weibo_links(self):
        for url in ("https://weibo.com/tv/show/1034:5063335004274724",
                    "https://video.weibo.com/show?fid=1034:5356898405253160",
                    "https://weibo.com/1234567890/AbCdEf",
                    "https://m.weibo.cn/detail/5063335004274724"):
            got = fetchers.find_links(url, ALL_ON, 3)
            self.assertEqual(got and got[0][0], "weibo", url)

    def test_clean_title_falls_back_when_url(self):
        import cnvideo
        self.assertEqual(cnvideo._clean_title({"title": "正常标题"}), "正常标题")
        info = {"title": "https://video.weibo.com/show?fid=1",
                "description": "关于见面会 后面还有话", "uploader": "某博主"}
        self.assertEqual(cnvideo._clean_title(info), "关于见面会")
        self.assertEqual(cnvideo._clean_title({"title": "", "uploader": "某博主"}), "某博主")

    def test_cn_links_detected(self):
        cases = {
            "https://www.bilibili.com/video/BV119Hg6aE87": "bilibili",
            "https://b23.tv/iVrYSRK": "bilibili",
            "https://v.douyin.com/abc123": "douyin",
            "https://www.douyin.com/video/7300000000000000000": "douyin",
            "https://www.kuaishou.com/short-video/3xabc": "kuaishou",
            "https://www.ixigua.com/7300000000000000000": "ixigua",
            "https://v.qq.com/x/cover/mzc00200zsqz54y": "vqq",
            "https://v.youku.com/v_show/id_XNTk=": "youku",
            "https://www.iqiyi.com/v_abc123": "iqiyi",
            "https://www.xiaohongshu.com/explore/abc123": "xiaohongshu",
        }
        for url, want in cases.items():
            got = fetchers.find_links(url, ALL_ON, 3)
            self.assertEqual(got and got[0][0], want, url)


class TestCleanSite(unittest.TestCase):
    """og:site_name 常带整句标题，要压成短站名。"""

    def test_takes_head_segment(self):
        self.assertEqual(fetchers.clean_site("少数派 - 高品质数字消费指南"), "少数派")
        self.assertEqual(fetchers.clean_site("BBC News | Breaking news"), "BBC News")
        self.assertEqual(fetchers.clean_site("知乎 · 有问题就会有答案"), "知乎")

    def test_keeps_plain_names(self):
        self.assertEqual(fetchers.clean_site("The GitHub Blog"), "The GitHub Blog")
        self.assertEqual(fetchers.clean_site(""), "")

    def test_punycode_to_chinese(self):
        self.assertEqual(fetchers.pretty_host("xn--fiqs8s"), "中国")
        self.assertEqual(fetchers.pretty_host("xn--gmq282eogn.xn--fiqs8s"), "人民网.中国")
        self.assertEqual(fetchers.pretty_host("www.example.com"), "www.example.com")
        self.assertEqual(fetchers.pretty_host("xn--bad-"), "xn--bad-")   # 转不了原样返回

    def test_placeholder_description_dropped(self):
        self.assertIsNone(fetchers.clean_desc("视频播放量 {$0}、弹幕量 {$1}"))
        self.assertEqual(fetchers.clean_desc("正常描述"), "正常描述")
        self.assertIsNone(fetchers.clean_desc(""))


class _FakeResp:
    def __init__(self, text, url, ctype="text/html; charset=utf-8"):
        self.status_code = 200
        self.text = text
        self.content = text.encode()
        self.url = url
        self.headers = {"content-type": ctype}


class _FakeClient:
    def __init__(self, resp):
        self.resp = resp

    async def get(self, url, **kw):
        return self.resp


class TestFetchOgWeb(unittest.TestCase):
    HTML = """<html><head>
      <meta property="og:title" content="一篇文章">
      <meta property="og:description" content="摘要内容">
      <meta property="og:site_name" content="示例站">
      <meta property="og:image" content="/img/cover.png">
      <meta property="article:published_time" content="2026-10-30T10:00:00Z">
      <link rel="icon" href="/favicon.ico">
    </head><body></body></html>"""

    def test_relative_image_and_favicon_resolved(self):
        client = _FakeClient(_FakeResp(self.HTML, "https://example.com/post/1"))
        c = asyncio.run(fetchers.fetch_og(client, "web", "https://example.com/post/1"))
        self.assertEqual(c["title"], "一篇文章")
        self.assertEqual(c["images"], ["https://example.com/img/cover.png"])
        self.assertEqual(c["author"]["avatar"], "https://example.com/favicon.ico")
        # 徽章显示站名，作者行显示域名，避免同一句话出现两次
        self.assertEqual(c["author"]["name"], "example.com")
        self.assertIsNone(c["author"]["handle"])
        self.assertEqual(c["platform_name"], "示例站")
        self.assertTrue(c["time"].startswith("2026-10-30"))

    def test_non_html_rejected(self):
        client = _FakeClient(_FakeResp("xx", "https://example.com/a", ctype="image/png"))
        with self.assertRaises(fetchers.FetchError):
            asyncio.run(fetchers.fetch_og(client, "web", "https://example.com/a"))

    def test_cert_error_falls_back_to_http(self):
        """中文域名证书常不匹配，https 失败要自动降级 http。"""
        class CertFailClient:
            def __init__(self):
                self.urls = []

            async def get(self, url, **kw):
                self.urls.append(url)
                if url.startswith("https://"):
                    import httpx
                    raise httpx.ConnectError(
                        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
                return _FakeResp(TestFetchOgWeb.HTML, "http://example.com/post/1")

        client = CertFailClient()
        c = asyncio.run(fetchers.fetch_og(client, "web", "https://example.com/post/1"))
        self.assertEqual(client.urls, ["https://example.com/post/1", "http://example.com/post/1"])
        self.assertEqual(c["title"], "一篇文章")

    def test_login_wall_rejected(self):
        html = "<html><head><title>Log in</title></head></html>"
        client = _FakeClient(_FakeResp(html, "https://example.com/a"))
        with self.assertRaises(fetchers.FetchError):
            asyncio.run(fetchers.fetch_og(client, "web", "https://example.com/a"))


class TestPlatformRegistry(unittest.TestCase):
    """抓取器、配置项、图标三处必须对得上，漏一个就会出现「开关不生效」或 KeyError。"""

    def test_every_pattern_key_has_config_item(self):
        # og 是兜底规则，具体站点名由 OG_SITES 映射，单独在下面校验
        for key, _ in fetchers.LINK_PATTERNS:
            if key == "og":
                continue
            self.assertIn(key, PLATFORM_ITEMS, f"平台 {key} 有抓取规则但配置里没有开关")

    def test_every_og_site_has_config_item(self):
        for name in set(fetchers.OG_SITES.values()):
            self.assertIn(name, PLATFORM_ITEMS, f"OG 站点 {name} 配置里没有开关")

    def test_every_config_item_has_platform_meta(self):
        for name in PLATFORM_ITEMS:
            self.assertIn(name, fetchers.PLATFORMS, f"配置项 {name} 没有平台名/配色")

    def test_every_platform_has_icon(self):
        for name in PLATFORM_ITEMS:
            self.assertIn(name, fetchers_icons(), f"平台 {name} 没有图标")


def fetchers_icons():
    import render

    return render.ICONS


class TestTwitchTarget(unittest.TestCase):
    """Twitch 链接解析：频道、切片、目录页要分得清。"""

    def test_channel(self):
        for url in ("https://www.twitch.tv/shroud", "https://twitch.tv/xqc?sr=a",
                    "https://twitch.tv/xqc/videos"):
            self.assertEqual(fetchers.twitch_target(url), ("channel", url.split("/")[3].split("?")[0]))

    def test_clip(self):
        self.assertEqual(fetchers.twitch_target("https://clips.twitch.tv/AbcDef"),
                         ("clip", "AbcDef"))
        self.assertEqual(fetchers.twitch_target("https://www.twitch.tv/xqc/clip/AbcDef"),
                         ("clip", "AbcDef"))

    def test_reserved_pages_fall_back_to_og(self):
        for url in ("https://www.twitch.tv/directory", "https://www.twitch.tv/videos/123",
                    "https://www.twitch.tv/"):
            self.assertEqual(fetchers.twitch_target(url), ("og", None), url)

    def test_bare_host(self):
        self.assertEqual(fetchers.twitch_target("https://twitch.tv"), ("og", None))


class TestLinkDedupe(unittest.TestCase):
    """同一条帖子带参数、换镜像域名，都只能算一条。"""

    def test_tracking_params_ignored(self):
        txt = ("https://x.com/a/status/123?a=xx&s=20 "
               "https://x.com/a/status/123")
        self.assertEqual(len(fetchers.find_links(txt, ALL_ON, 5)), 1)

    def test_mirror_hosts_collapsed(self):
        for mirror in ("twitter.com", "vxtwitter.com", "fixupx.com"):
            txt = f"https://{mirror}/a/status/123 https://x.com/a/status/123"
            self.assertEqual(len(fetchers.find_links(txt, ALL_ON, 5)), 1, mirror)

    def test_youtu_be_matches_watch_url(self):
        txt = "https://youtu.be/dQw4w9WgXcQ https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(len(fetchers.find_links(txt, ALL_ON, 5)), 1)

    def test_different_posts_still_separate(self):
        txt = "https://youtu.be/dQw4w9WgXcQ https://youtu.be/aaaaaaaaaaa"
        self.assertEqual(len(fetchers.find_links(txt, ALL_ON, 5)), 2)

    def test_same_owner_different_repos(self):
        txt = "https://github.com/o/r1 https://github.com/o/r2"
        self.assertEqual(len(fetchers.find_links(txt, ALL_ON, 5)), 2)

    def test_canonical_url_shape(self):
        self.assertEqual(
            fetchers.canonical_url("https://x.com/a/status/1?a=1&s=20#top"),
            "https://x.com/a/status/1")
        self.assertEqual(
            fetchers.canonical_url("https://twitter.com/a/status/1/"),
            "https://x.com/a/status/1")


class TestFormatting(unittest.TestCase):
    def test_compact(self):
        self.assertEqual(fetchers.compact(1234), "1,234")
        self.assertEqual(fetchers.compact(12345), "1.2万")
        self.assertEqual(fetchers.compact(123456789), "1.2亿")
        self.assertIsNone(fetchers.compact(None))
        self.assertIsNone(fetchers.compact("abc"))

    def test_fmt_time(self):
        # 1700000000 = 2023-11-14 22:13:20 UTC -> 北京时间次日 06:13
        self.assertEqual(fetchers.fmt_time(1700000000), "2023-11-15 06:13")
        self.assertEqual(fetchers.fmt_time("2024-05-01T12:00:00Z"), "2024-05-01 20:00")
        self.assertIsNone(fetchers.fmt_time(None))
        self.assertIsNone(fetchers.fmt_time(""))

    def test_duration(self):
        self.assertEqual(fetchers.duration(212), "3:32")
        self.assertEqual(fetchers.duration(3725), "1:02:05")
        self.assertIsNone(fetchers.duration(0))
        self.assertIsNone(fetchers.duration(None))

    def test_stat_drops_empty(self):
        self.assertIsNone(fetchers.stat("赞", None))
        self.assertIsNone(fetchers.stat("赞", ""))
        self.assertEqual(fetchers.stat("赞", 12345), ["赞", "1.2万"])
        self.assertEqual(fetchers.stat("时长", "3:32"), ["时长", "3:32"])

    def test_card_defaults_and_stat_filter(self):
        c = fetchers.card("github", "https://github.com/o/r",
                          stats=[None, ["标星", "1"], None])
        self.assertEqual(c["platform_name"], "GitHub")
        self.assertEqual(c["stats"], [["标星", "1"]])
        self.assertEqual(c["comments"], [])
        self.assertEqual(c["images"], [])


class TestParseMeta(unittest.TestCase):
    def test_og_tags(self):
        html = """<html><head>
        <meta property="og:title" content="标题 &amp; 更多">
        <meta property="og:description" content="描述">
        <meta name="twitter:image" content="https://example.com/a.jpg">
        <title>备用标题</title></head></html>"""
        meta = fetchers.parse_meta(html)
        self.assertEqual(meta["og:title"], "标题 & 更多")
        self.assertEqual(meta["og:description"], "描述")
        self.assertEqual(meta["twitter:image"], "https://example.com/a.jpg")
        self.assertEqual(meta["title"], "备用标题")

    def test_first_occurrence_wins(self):
        html = ('<meta property="og:title" content="第一个">'
                '<meta property="og:title" content="第二个">')
        self.assertEqual(fetchers.parse_meta(html)["og:title"], "第一个")

    def test_empty_page(self):
        self.assertEqual(fetchers.parse_meta(""), {})


class TestPagination(unittest.TestCase):
    def test_short_section_single_page(self):
        pages = fetchers.paginate([{"title": "甲", "level": 2, "text": "短"}], page_chars=100)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0][0]["title"], "甲")

    def test_long_section_splits(self):
        sec = {"title": "乙", "level": 2, "text": "\n".join(["段落" * 10] * 20)}
        pages = fetchers.paginate([sec], page_chars=100)
        self.assertGreater(len(pages), 1)
        # 续页标题带「（续）」
        self.assertTrue(any("（续）" in b["title"] for p in pages for b in p))

    def test_single_huge_paragraph_hard_cut(self):
        sec = {"title": "", "level": 2, "text": "字" * 250}
        pages = fetchers.paginate([sec], page_chars=100)
        self.assertGreaterEqual(len(pages), 3)


class TestNeedsTranslation(unittest.TestCase):
    """翻译判定：日/韩一律翻，英文按字母数，中文不翻。"""

    def test_english_needs_translation(self):
        self.assertTrue(fetchers.needs_translation("just setting up my twttr"))
        self.assertTrue(fetchers.needs_translation("Hello 世界 this is a test"))

    def test_chinese_not_translated(self):
        self.assertFalse(fetchers.needs_translation("可怜的大肥鱼，谁给你调成这样的"))
        self.assertFalse(fetchers.needs_translation("这是一条中文微博，不需要翻译"))

    def test_japanese_and_korean(self):
        self.assertTrue(fetchers.needs_translation("これはテストです"))
        self.assertTrue(fetchers.needs_translation("안녕하세요"))      # 短句也要翻
        self.assertTrue(fetchers.needs_translation("テスト"))

    def test_too_short_or_empty(self):
        self.assertFalse(fetchers.needs_translation(""))
        self.assertFalse(fetchers.needs_translation(None))
        self.assertFalse(fetchers.needs_translation("OK"))
        self.assertFalse(fetchers.needs_translation("12345"))


class TestTextCleaning(unittest.TestCase):
    def test_flatten_collapses_whitespace(self):
        raw = "Hi\n@jack\n, I made  offer:\n\n\nhttps://v.cent.co/x\n@cent"
        self.assertEqual(fetchers.flatten(raw), "Hi @jack , I made offer: https://v.cent.co/x @cent")
        self.assertEqual(fetchers.flatten(None), "")
        self.assertEqual(fetchers.flatten("  "), "")

    def test_steam_plain_strips_bbcode(self):
        raw = "[b]标题[/b] 正文 [url=https://a.b]链接[/url] [spoiler]剧透[/spoiler]"
        out = fetchers._steam_plain(raw)
        for token in ("[b]", "[/b]", "[url", "[/url]", "[spoiler]"):
            self.assertNotIn(token, out)
        self.assertIn("标题", out)
        self.assertIn("链接", out)

    def test_wiki_plain_drops_refs(self):
        out = fetchers._wiki_plain("正文<ref>来源</ref>继续")
        self.assertNotIn("<ref>", out)
        self.assertIn("正文", out)


class TestPrivateGuard(unittest.TestCase):
    """真正发请求前按解析结果拦内网，重定向的每一跳也要查。"""

    def setUp(self):
        self._orig = fetchers._resolve
        table = {"example.com": ["93.184.215.14"], "evil.example": ["127.0.0.1"],
                 "127.0.0.1.nip.io": ["127.0.0.1"], "fake.example": ["198.18.0.7"],
                 "v6.example": ["::ffff:10.0.0.1"]}

        async def resolve(host, port):
            return table.get(host, ["93.184.215.14"])
        fetchers._resolve = resolve

    def tearDown(self):
        fetchers._resolve = self._orig

    def _get(self, url, handler):
        async def go():
            import httpx
            async with fetchers.make_client(transport=httpx.MockTransport(handler)) as c:
                return await c.get(url)
        return asyncio.run(go())

    def test_blocked_ip(self):
        for ip in ("127.0.0.1", "10.1.2.3", "172.17.0.1", "192.168.1.1", "169.254.169.254",
                   "100.64.0.1", "0.0.0.0", "::1", "fe80::1%en0", "::ffff:127.0.0.1", "224.0.0.1", "bad"):
            self.assertTrue(fetchers._blocked_ip(ip), ip)
        for ip in ("93.184.215.14", "1.1.1.1", "2606:4700::1111", "198.18.0.7"):
            self.assertFalse(fetchers._blocked_ip(ip), ip)

    def test_public_ok(self):
        import httpx
        r = self._get("https://example.com/", lambda req: httpx.Response(200, text="ok"))
        self.assertEqual(r.text, "ok")

    def test_fake_ip_ok(self):
        import httpx
        r = self._get("https://fake.example/", lambda req: httpx.Response(200, text="ok"))
        self.assertEqual(r.text, "ok")

    def test_domain_resolving_to_loopback(self):
        import httpx
        for url in ("http://127.0.0.1.nip.io:6185/", "http://v6.example/"):
            with self.assertRaises(fetchers.FetchError):
                self._get(url, lambda req: httpx.Response(200, text="leak"))

    def test_redirect_to_internal(self):
        import httpx
        hits = []

        def handler(req):
            hits.append(req.url.host)
            if req.url.host == "example.com":
                return httpx.Response(302, headers={"Location": "http://evil.example:6185/"})
            return httpx.Response(200, text="leak")
        with self.assertRaises(fetchers.FetchError):
            self._get("https://example.com/", handler)
        self.assertEqual(hits, ["example.com"])


class TestSubprocessCleanup(unittest.TestCase):
    """外层总超时取消任务时，子进程也要被杀掉，不能留在后台。"""

    def test_cancel_kills_process(self):
        import cnvideo
        holder = {}

        async def go():
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "import time; time.sleep(30)",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            holder["proc"] = proc
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(cnvideo._communicate(proc, 60, "x"), 0.3)
            return proc.returncode
        self.assertIsNotNone(asyncio.run(go()))

    def test_own_timeout(self):
        import cnvideo

        async def go():
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "import time; time.sleep(30)",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            with self.assertRaises(fetchers.FetchError):
                await cnvideo._communicate(proc, 0.3, "超时")
            return proc.returncode
        self.assertIsNotNone(asyncio.run(go()))


class TestQQMiniApp(unittest.TestCase):
    """QQ 小程序分享卡片：qqdocurl 是背后真实网页，m.q.qq.com 是客户端专用页。"""

    ARK = {
        "app": "com.tencent.miniapp_01",
        "desc": "",
        "view": "view_8C8E89B49BE609866298ADDFF2DBABA4",
        "ver": "1.0.0.19",
        "prompt": "[QQ小程序]哔哩哔哩",
        "meta": {"detail_1": {
            "appid": "1109937557",
            "title": "哔哩哔哩",
            "desc": "哔哩哔哩(゜-゜)つロ 干杯~-bilibili",
            "icon": "http://miniapp.gtimg.cn/public/appicon/xxx.png",
            "preview": "https://i0.hdslb.com/bfs/archive/xxx.jpg",
            "url": "m.q.qq.com/a/s/abcdef",
            "qqdocurl": "https://b23.tv/AbCdEf?share_source=qq",
        }},
    }

    def test_reads_qqdocurl(self):
        text = "[CQ:json,data=" + json.dumps(self.ARK, ensure_ascii=False) + "]"
        got = fetchers.qq_miniapps(text)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["real"], "https://b23.tv/AbCdEf?share_source=qq")
        self.assertEqual(got[0]["page"], "https://m.q.qq.com/a/s/abcdef")
        self.assertEqual(got[0]["title"], "哔哩哔哩")

    def test_real_url_goes_to_platform(self):
        got = fetchers.qq_miniapps(json.dumps(self.ARK, ensure_ascii=False))
        self.assertEqual(fetchers.find_links(got[0]["real"], ALL_ON)[0][0], "bilibili")

    def test_native_miniapp_has_no_real_url(self):
        ark = json.loads(json.dumps(self.ARK))
        ark["meta"]["detail_1"].pop("qqdocurl")
        got = fetchers.qq_miniapps(json.dumps(ark, ensure_ascii=False))
        self.assertEqual(got[0]["real"], "")
        self.assertEqual(got[0]["url"], "https://m.q.qq.com/a/s/abcdef")

    def test_qqdocurl_on_client_host_is_ignored(self):
        ark = json.loads(json.dumps(self.ARK))
        ark["meta"]["detail_1"]["qqdocurl"] = "https://m.q.qq.com/a/p/1109937557"
        got = fetchers.qq_miniapps(json.dumps(ark, ensure_ascii=False))
        self.assertEqual(got[0]["real"], "")

    def test_news_card_is_not_miniapp(self):
        ark = {"app": "com.tencent.structmsg", "meta": {"news": {"title": "新闻", "jumpUrl": "https://example.com/a"}}}
        self.assertEqual(fetchers.qq_miniapps(json.dumps(ark, ensure_ascii=False)), [])

    def test_card_uses_ark_info(self):
        got = fetchers.qq_miniapps(json.dumps(self.ARK, ensure_ascii=False))
        c = fetchers.qq_miniapp_card(got[0]["url"], got[0])
        self.assertEqual(c["platform"], "qqminiapp")
        self.assertEqual(c["title"], "哔哩哔哩")
        self.assertEqual(c["images"], ["https://i0.hdslb.com/bfs/archive/xxx.jpg"])
        self.assertTrue(c["note"])


if __name__ == "__main__":
    unittest.main()
