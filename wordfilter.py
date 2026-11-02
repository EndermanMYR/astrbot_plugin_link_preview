"""敏感词屏蔽：词表文件 + 配置里追加的词，文件改了自动重新读取。"""

import os
import re
import shutil
from pathlib import Path

BUNDLED = Path(__file__).parent / "sensitive_words.txt"
BUNDLED_RESTRICTED = Path(__file__).parent / "restricted_words.txt"

# 中文匹配前先去掉常被插在字中间的符号：空格、零宽字符、间隔号、星号、斜杠等。
# 句号、逗号这类断句标点不去掉，免得「…在台。独自…」被拼成「台独」误判。
SEP_RE = re.compile(r"[ \t　​-‏⁠﻿·•・.*_\-|/\\~`'\"“”‘’]+")
ASCII_RE = re.compile(r"[a-z0-9 .'-]+")


def _norm(text):
    return SEP_RE.sub("", str(text or "").lower())


def parse_words(raw):
    """每行一个词（也接受逗号、分号分隔），# 开头的行是注释。"""
    words = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words += [w.strip() for w in re.split(r"[,;，；]+", line) if w.strip()]
    return words


class WordFilter:
    def __init__(self, path, extra=(), bundled=BUNDLED):
        self.path = Path(path) if path else None
        self.bundled = bundled
        self.extra = [str(w).strip() for w in extra or () if str(w).strip()]
        self._mtime = None
        self._ascii, self._cjk, self._raw = [], [], []
        self.ensure_file()
        self.reload()

    def ensure_file(self):
        """词表文件不存在时，用插件自带的那份初始化。"""
        if self.path and not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.bundled, self.path)

    def reload(self):
        words = list(self.extra)
        if self.path:
            try:
                self._mtime = os.path.getmtime(self.path)
                words += parse_words(self.path.read_text(encoding="utf-8"))
            except OSError:
                self._mtime = None
        self._raw = sorted(set(words), key=len, reverse=True)
        self._ascii = [w.lower() for w in self._raw if ASCII_RE.fullmatch(w.lower())]
        self._cjk = [_norm(w) for w in self._raw if not ASCII_RE.fullmatch(w.lower()) and _norm(w)]

    def _fresh(self):
        if self.path:
            try:
                if os.path.getmtime(self.path) != self._mtime:
                    self.reload()
            except OSError:
                pass

    @property
    def count(self):
        self._fresh()
        return len(self._raw)

    def find(self, *texts):
        """返回命中的词；没命中返回 None。"""
        self._fresh()
        joined = "\n".join(str(t or "") for t in texts)
        low = joined.lower()
        for w in self._ascii:
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
                return w
        flat = _norm(joined)
        for w in self._cjk:
            if w in flat:
                return w
        return None

    def mask(self, text):
        """把原文里直接出现的敏感词换成 ■（插字写法打不了码，交给 find 再判一次）。"""
        if not text:
            return text
        self._fresh()
        out = str(text)
        for w in self._raw:
            out = re.sub(re.escape(w), "■" * len(w), out, flags=re.I)
        return out
