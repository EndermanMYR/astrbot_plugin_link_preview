"""fetchers 的纯函数测试：不联网、不需要 AstrBot。"""

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


if __name__ == "__main__":
    unittest.main()
