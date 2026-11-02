"""render 的版式与裁边测试：不联网、不出图，只验 HTML 与裁切逻辑。"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests._stub import install  # noqa: E402

install()

import render  # noqa: E402

CARD = {
    "platform": "x", "platform_name": "X", "color": "#000000",
    "url": "https://x.com/a/status/1", "title": None, "text": "hi",
    "author": {"name": "a", "handle": "@a", "avatar": None, "bio": ""},
    "images": [], "stats": [["回复", "1"]], "tags": [], "time": "2026-01-01 00:00",
    "comments": [], "quote": None, "video": False, "duration": None,
    "sensitive": False, "note": None, "comments_mode": False, "blur": False,
    "domain": "x.com", "short_url": "x.com/a/status/1", "icon": "X",
    "no_comments_reason": None,
}


class TestBuildHtml(unittest.TestCase):
    def test_t2i_class_on_body(self):
        html = render.build_html(CARD, "dark")
        self.assertIn('class="dark t2i"', html)

    def test_t2i_can_be_disabled(self):
        html = render.build_html(CARD, "dark", t2i=False)
        self.assertIn('class="dark"', html)
        self.assertNotIn("t2i", html.split("<body")[1][:80])

    def test_latin_font_comes_before_cjk(self):
        """远端 Chromium 缺 Noto CJK 时会退到全角拉丁的字体，DejaVu/sans-serif 必须排在前面。"""
        html = render.build_html(CARD, "dark")
        stack = html.split("font-family:", 1)[1].split(";", 1)[0]
        self.assertLess(stack.index("DejaVu Sans"), stack.index("Noto Sans CJK SC"))
        self.assertLess(stack.index("sans-serif"), stack.index("Noto Sans CJK SC"))

    def test_no_local_font_face(self):
        """不要再用 local() 取字体，远端不一定装了。"""
        self.assertNotIn("@font-face", render.build_html(CARD, "dark"))
        self.assertNotIn("PunctFix", render.build_html(CARD, "dark"))

    def test_card_fills_t2i_viewport(self):
        html = render.build_html(CARD, "dark")
        self.assertIn("body.t2i { width: 800px; }", html)


class TestMediaLayout(unittest.TestCase):
    """竖图必须走纵向堆叠，否则 cover 会把上下裁掉。"""

    def test_portrait_needs_stack(self):
        self.assertTrue(render.media_needs_stack([(648, 1280)]))
        self.assertTrue(render.media_needs_stack([(800, 600), (648, 1280)]))

    def test_landscape_and_square_use_grid(self):
        self.assertFalse(render.media_needs_stack([(1280, 720)]))
        self.assertFalse(render.media_needs_stack([(600, 600), (800, 400)]))

    def test_empty_or_unknown_sizes(self):
        self.assertFalse(render.media_needs_stack([]))
        self.assertFalse(render.media_needs_stack([(0, 0)]))

    def test_threshold(self):
        self.assertFalse(render.media_needs_stack([(100, 120)]))   # 1.2 仍算横/方
        self.assertTrue(render.media_needs_stack([(100, 130)]))    # 1.3 算竖图

    def test_template_renders_stack_class(self):
        card = dict(CARD, images=["data:image/jpeg;base64,xx"], media_tall=True)
        html = render.build_html(card, "dark")
        self.assertIn("media n1 stack", html)

    def test_template_without_tall(self):
        card = dict(CARD, images=["data:image/jpeg;base64,xx"], media_tall=False)
        self.assertNotIn(" stack", render.build_html(card, "dark").split("<body")[1][:2000])


class TestTranslationBlock(unittest.TestCase):
    def test_renders_translation_block(self):
        card = dict(CARD, translation="这是译文")
        html = render.build_html(card, "dark")
        self.assertIn('class="trans"', html)
        self.assertIn("这是译文", html)

    def test_no_block_without_translation(self):
        html = render.build_html(dict(CARD, translation=None), "dark")
        self.assertNotIn('class="trans"', html)


class TestT2iOptions(unittest.TestCase):
    def test_returns_full_page_jpeg(self):
        opt = render.t2i_options()
        self.assertEqual(opt["type"], "jpeg")
        self.assertTrue(opt["full_page"])
        self.assertGreaterEqual(opt["quality"], 90)


class TestCropImage(unittest.TestCase):
    def _make(self, w, h, box, bg=(12, 11, 22)):
        from PIL import Image

        im = Image.new("RGB", (w, h), bg)
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                im.putpixel((x, y), (200, 60, 60))
        path = os.path.join(tempfile.mkdtemp(), "t.jpg")
        im.save(path, "JPEG", quality=95)
        return path

    def test_crops_uniform_border(self):
        from PIL import Image

        path = self._make(400, 300, (50, 40, 250, 160))
        render.crop_image(path, pad=0)
        with Image.open(path) as im:
            w, h = im.size
        self.assertLess(w, 400)
        self.assertLess(h, 300)
        self.assertGreaterEqual(w, 200)
        self.assertGreaterEqual(h, 120)

    def test_pad_keeps_margin(self):
        from PIL import Image

        path = self._make(400, 300, (50, 40, 250, 160))
        render.crop_image(path, pad=10)
        with Image.open(path) as im:
            w, h = im.size
        self.assertGreaterEqual(w, 220)
        self.assertGreaterEqual(h, 140)

    def test_all_background_is_noop(self):
        from PIL import Image

        path = self._make(200, 200, (0, 0, 0, 0))
        render.crop_image(path)
        with Image.open(path) as im:
            self.assertEqual(im.size, (200, 200))

    def test_missing_file_does_not_raise(self):
        self.assertEqual(render.crop_image("/tmp/definitely-not-here.jpg"), "/tmp/definitely-not-here.jpg")


if __name__ == "__main__":
    unittest.main()
