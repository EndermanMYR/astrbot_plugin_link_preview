"""测试辅助：AstrBot 不在环境里时，注入一个假的 astrbot.api.logger。

生产代码里 logger 是直接从 `astrbot.api` 导入的（市场安全审查要求，不留标准库兜底），
所以脱离 AstrBot 跑测试时 import 会失败。这里只在测试进程内伪造，不影响插件运行。
"""

import logging
import sys
import types

STUB_LOGGER = logging.getLogger("astrbot.test")


def install():
    """装了真的 AstrBot 就直接用，没装才注入假模块。重复调用无副作用。"""
    if "astrbot.api" in sys.modules:
        return
    try:
        import astrbot.api  # noqa: F401
        return
    except ImportError:
        pass

    pkg = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = STUB_LOGGER
    pkg.api = api
    sys.modules["astrbot"] = pkg
    sys.modules["astrbot.api"] = api
