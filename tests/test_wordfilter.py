"""敏感词过滤器测试：纯本地，不联网。"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests._stub import install  # noqa: E402

install()

import wordfilter  # noqa: E402


class TestParseWords(unittest.TestCase):
    def test_ignores_comments_and_blank_lines(self):
        raw = "# 注释\n\n词一\n  # 缩进注释\n词二\n"
        self.assertEqual(wordfilter.parse_words(raw), ["词一", "词二"])

    def test_splits_on_commas(self):
        self.assertEqual(wordfilter.parse_words("甲,乙，丙;丁；戊"), ["甲", "乙", "丙", "丁", "戊"])

    def test_empty(self):
        self.assertEqual(wordfilter.parse_words(""), [])
        self.assertEqual(wordfilter.parse_words(None), [])


class TestWordFilter(unittest.TestCase):
    def setUp(self):
        self.f = wordfilter.WordFilter(None, ["坏词", "badword"])

    def test_hits(self):
        self.assertEqual(self.f.find("这里有个坏词"), "坏词")
        self.assertEqual(self.f.find("a badword here"), "badword")
        self.assertIsNone(self.f.find("很干净的文本"))

    def test_ignores_separators_between_cjk(self):
        # 空格、零宽字符、间隔号插在字中间也能认出来
        for text in ("坏 词", "坏　词", "坏·词", "坏*词", "坏\u200b词"):
            self.assertEqual(self.f.find(text), "坏词", text)

    def test_ascii_needs_word_boundary(self):
        # badwordx 不该命中 badword
        self.assertIsNone(self.f.find("badwordx"))
        self.assertIsNone(self.f.find("xbadword"))

    def test_checks_multiple_fields(self):
        self.assertIsNone(self.f.find("标题", "正文"))
        self.assertEqual(self.f.find("标题", "正文里有坏词"), "坏词")

    def test_mask(self):
        self.assertEqual(self.f.mask("这是坏词"), "这是■■")
        self.assertEqual(self.f.mask("干净"), "干净")
        self.assertEqual(self.f.mask(""), "")

    def test_count(self):
        self.assertEqual(self.f.count, 2)

    def test_case_insensitive(self):
        self.assertEqual(self.f.find("BADWORD"), "badword")


class TestFileHandling(unittest.TestCase):
    def test_creates_file_from_bundled(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "political.txt"
            wordfilter.WordFilter(str(target), [])
            self.assertTrue(target.exists(), "词表文件不存在时应从内置词表复制")
            self.assertGreater(target.stat().st_size, 0)

    def test_picks_up_file_changes(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "words.txt"
            target.write_text("旧词\n", encoding="utf-8")
            f = wordfilter.WordFilter(str(target), [])
            self.assertEqual(f.find("这里有旧词"), "旧词")
            self.assertIsNone(f.find("这里有新词"))

            # 改了文件（mtime 变化）后应自动重新加载
            import time

            time.sleep(0.01)
            target.write_text("新词\n", encoding="utf-8")
            os.utime(target, None)
            self.assertEqual(f.find("这里有新词"), "新词")

    def test_bundled_wordlists_loadable(self):
        for path in (wordfilter.BUNDLED, wordfilter.BUNDLED_R18):
            words = wordfilter.parse_words(path.read_text(encoding="utf-8"))
            self.assertGreater(len(words), 100, f"{path.name} 词表太小，可能读错了")


if __name__ == "__main__":
    unittest.main()
