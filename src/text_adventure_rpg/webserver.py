"""Web 服务入口：console script ``text-rpg-web`` 的 main()。

与既有 ``text-rpg`` / ``text-full-rpg`` 并行的第三个入口——``__main__.py``
被 005 Agent Loop 版占用，本文件是纯新增，不动任何现有模块。
"""

from __future__ import annotations

import uvicorn

from .config import load_settings
from .main import create_app


def main() -> int:
    """按环境配置启动 Web 服务（默认 127.0.0.1:8805）。"""
    settings = load_settings()
    app = create_app(settings)
    uvicorn.run(app, host="127.0.0.1", port=settings.app_port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
