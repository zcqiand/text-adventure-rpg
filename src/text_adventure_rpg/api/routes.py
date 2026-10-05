"""REST 路由：会话型战斗 RPG 的 HTTP 面。

薄壳层：异常翻译（服务层异常 → HTTP 状态码）+ 视图组装，不掺业务逻辑。
服务实例挂在 ``app.state.service``（create_app 注入），测试可整体替换。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .. import game
from ..character import make_character
from ..game_service import (
    GameOverError,
    GameService,
    InvalidInputError,
    UnknownSessionError,
)

router = APIRouter(prefix="/api")


class CreateGameIn(BaseModel):
    """建局请求：class 必填；name / scene_id 可选。

    ``class`` 是 Python 关键字，字段名用 ``class_`` + 别名承接前端 JSON 键。
    """

    model_config = ConfigDict(populate_by_name=True)

    class_: str = Field(default="", alias="class")
    name: str = "冒险者"
    scene_id: str = "forest"


class CommandIn(BaseModel):
    input: str


class SlotIn(BaseModel):
    slot: str


def _service(request: Request) -> GameService:
    return request.app.state.service


@router.get("/health")
def health(request: Request):
    settings = request.app.state.settings
    return {"ok": True, "mode": settings.llm_mode}


@router.get("/classes")
def list_classes():
    """三职业菜单：label 与 CLI 菜单同源（game._CLASS_MENU），属性来自 make_character。"""
    views = []
    for _key, cls, label in game._CLASS_MENU:
        template = make_character("_", cls)
        views.append(
            {
                "class": cls.value,
                "label": label,
                "stats": {
                    "max_hp": template.max_hp,
                    "max_mp": template.max_mp,
                    "atk": template.atk,
                    "def_": template.def_,
                },
            }
        )
    return views


@router.post("/games", status_code=201)
def create_game(body: CreateGameIn, request: Request):
    service = _service(request)
    try:
        session = service.create(body.class_, name=body.name, scene_id=body.scene_id)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": session.id, "created_at": session.created_at, "state": service.view(session)}


@router.get("/games")
def list_games(request: Request):
    service = _service(request)
    return [service.summary(s) for s in service.store.all_newest_first()]


@router.get("/games/{sid}")
def get_game(sid: str, request: Request):
    service = _service(request)
    session = service.store.get(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"id": session.id, "created_at": session.created_at, "state": service.view(session)}


@router.post("/games/{sid}/command")
def run_command(sid: str, body: CommandIn, request: Request):
    service = _service(request)
    try:
        messages = service.command(sid, body.input)
    except UnknownSessionError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except (InvalidInputError, GameOverError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = service.store.get(sid)
    return {
        "messages": messages,
        "state": service.view(session),
        "game_over": session.game_over,
    }


@router.post("/games/{sid}/save")
def save_game(sid: str, body: SlotIn, request: Request):
    try:
        return _service(request).save(sid, body.slot)
    except UnknownSessionError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/games/{sid}/load")
def load_game(sid: str, body: SlotIn, request: Request):
    service = _service(request)
    try:
        messages = service.load(sid, body.slot)
    except UnknownSessionError as exc:
        raise HTTPException(status_code=404, detail="会话不存在") from exc
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = service.store.get(sid)
    return {
        "messages": messages,
        "state": service.view(session),
        "game_over": session.game_over,
    }


@router.get("/saves")
def list_saves(request: Request):
    return _service(request).list_saves()
