"""应用工厂：组装 settings / narrator / service，挂到 app.state。

测试注入 mock narrator（确定性模板）与临时存档目录即可全链路离线；
live 由 :func:`build_narrator` 按 settings 接 OpenAI 兼容端点。
"""

from __future__ import annotations

from fastapi import FastAPI

from .api.routes import router
from .config import Settings, load_settings
from .game_service import GameService
from .llm_client import OpenAICompatNarrator
from .narrative import Narrator


def build_narrator(settings: Settings) -> Narrator:
    """按 LLM_MODE 构造叙事器：mock=本地确定性模板，live=OpenAI 兼容直调。"""
    if settings.llm_mode == "live":
        client = OpenAICompatNarrator(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
        return Narrator(client=client)
    return Narrator(client=None)


def create_app(
    settings: Settings | None = None,
    narrator: Narrator | None = None,
) -> FastAPI:
    """构造 FastAPI 应用。settings/narrator 均可注入（测试用）。"""
    resolved = settings if settings is not None else load_settings(environ=None)
    app = FastAPI(title="text-adventure-rpg Web API")
    app.state.settings = resolved
    app.state.narrator = narrator if narrator is not None else build_narrator(resolved)
    app.state.service = GameService(resolved.saves_dir, app.state.narrator)
    app.include_router(router)
    return app
