"""Web API e2e（TestClient，LLM_MODE=mock 全链路离线）。

战斗版（text-full-rpg 同一业务核）的 HTTP 面：health → classes → 建局 →
探索/战斗/存读档 → 异常分支。战斗确定性（variance=0）使伤害/胜负可精确断言；
服务层白盒（store 直改 HP/MP）用于覆盖降级与败北两个 CLI 里难以到达的分支。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from text_adventure_rpg.config import load_settings
from text_adventure_rpg.main import create_app
from text_adventure_rpg.narrative import Narrator


@pytest.fixture()
def client(tmp_path):
    settings = load_settings(
        environ={
            "LLM_MODE": "mock",
            "APP_SAVES_DIR": str(tmp_path / "saves"),
        },
        env_file=tmp_path / "no.env",
    )
    app = create_app(settings, narrator=Narrator(client=None))
    with TestClient(app) as c:
        yield c


def _new_game(client, cls="warrior", name="冒险者") -> str:
    r = client.post("/api/games", json={"class": cls, "name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _msg_join(messages: list[str]) -> str:
    return "\n".join(messages)


# ---- 基础 ----


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"


def test_classes_list(client):
    r = client.get("/api/classes")
    assert r.status_code == 200
    items = r.json()
    assert [c["class"] for c in items] == ["warrior", "mage", "rogue"]
    # 三职业差异化可量化（功能规格：同一敌人三职业初始属性差异）
    by = {c["class"]: c["stats"] for c in items}
    assert by["warrior"]["max_hp"] > by["mage"]["max_hp"]
    assert by["mage"]["max_mp"] > by["warrior"]["max_mp"]
    assert by["rogue"]["atk"] > by["warrior"]["atk"]
    # 菜单文案与 CLI 菜单一致
    labels = [c["label"] for c in items]
    assert any("战士" in l for l in labels)
    assert any("法师" in l for l in labels)
    assert any("盗贼" in l for l in labels)


# ---- 建局 ----


def test_create_game_defaults(client):
    r = client.post("/api/games", json={"class": "mage", "name": "梅林"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    assert body["created_at"]
    state = body["state"]
    assert state["hero"]["name"] == "梅林"
    assert state["hero"]["class"] == "mage"
    assert state["hero"]["max_mp"] == 100  # 法师高法力
    assert state["scene"]["id"] == "forest"
    assert state["pending_enemy"]["id"] == "wolf"
    assert state["battle"] is None
    assert state["game_over"] is False


def test_create_invalid_class_400(client):
    r = client.post("/api/games", json={"class": "bard"})
    assert r.status_code == 400
    assert "职业" in r.json()["detail"]


def test_create_unknown_scene_400(client):
    r = client.post("/api/games", json={"class": "warrior", "scene_id": "abyss"})
    assert r.status_code == 400
    assert "场景" in r.json()["detail"]


def test_create_rejects_blank_name(client):
    r = client.post("/api/games", json={"class": "warrior", "name": "   "})
    assert r.status_code == 400
    assert "名字" in r.json()["detail"]


# ---- 探索 ----


def test_go_south_moves_to_village(client):
    sid = _new_game(client, cls="rogue")
    # 未清场禁移动（CLI 同语义）：先打赢挡路的狼再南下
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    for _ in range(3):
        client.post(f"/api/games/{sid}/command", json={"input": "attack"})
    r = client.post(f"/api/games/{sid}/command", json={"input": "go south"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["scene"]["id"] == "village_gate"
    assert body["state"]["pending_enemy"] is None
    joined = _msg_join(body["messages"])
    assert "村庄" in joined


def test_go_blocked_by_enemy(client):
    sid = _new_game(client)
    r = client.post(f"/api/games/{sid}/command", json={"input": "go north"})
    assert r.status_code == 200
    body = r.json()
    # 位置不变 + 提示先战
    assert body["state"]["scene"]["id"] == "forest"
    assert any("挡住" in m for m in body["messages"])


def test_look_and_status(client):
    sid = _new_game(client)
    r = client.post(f"/api/games/{sid}/command", json={"input": "look"})
    assert r.status_code == 200
    assert any("森林" in m for m in r.json()["messages"])
    r = client.post(f"/api/games/{sid}/command", json={"input": "status"})
    assert r.status_code == 200
    assert any("HP" in m for m in r.json()["messages"])
    # state.log 随详情返回（前端刷新后可还原终端历史）
    detail = client.get(f"/api/games/{sid}").json()
    assert len(detail["state"]["log"]) >= 2


def test_unknown_command_becomes_message_not_error(client):
    sid = _new_game(client)
    r = client.post(f"/api/games/{sid}/command", json={"input": "dance"})
    assert r.status_code == 200
    assert any("未识别" in m for m in r.json()["messages"])


def test_empty_command_400(client):
    sid = _new_game(client)
    r = client.post(f"/api/games/{sid}/command", json={"input": "   "})
    assert r.status_code == 400


def test_unknown_session_404(client):
    assert client.get("/api/games/nope").status_code == 404
    r = client.post("/api/games/nope/command", json={"input": "look"})
    assert r.status_code == 404
    assert client.post("/api/games/nope/save", json={"slot": "s1"}).status_code == 404
    assert client.post("/api/games/nope/load", json={"slot": "s1"}).status_code == 404


# ---- 战斗 ----


def test_fight_and_attack_turns(client):
    sid = _new_game(client, cls="rogue")
    r = client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["battle"] is not None
    assert body["state"]["battle"]["enemy"]["name"] == "饥饿的灰狼"
    assert body["state"]["battle"]["enemy"]["hp"] == 40

    r = client.post(f"/api/games/{sid}/command", json={"input": "attack"})
    assert r.status_code == 200
    body = r.json()
    enemy = body["state"]["battle"]["enemy"]
    hero = body["state"]["hero"]
    # 盗贼 atk22 vs 狼 def5 → 17；狼 atk12 vs 盗贼 def9 → 3
    assert enemy["hp"] == 23
    assert hero["hp"] == 92
    assert any("17" in m for m in body["messages"])
    # 探索指令在战斗中被拦截
    r = client.post(f"/api/games/{sid}/command", json={"input": "go north"})
    assert r.status_code == 400
    assert "战斗" in r.json()["detail"]


def test_skill_costs_mp_and_outdamages(client):
    sid = _new_game(client, cls="mage")
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    r = client.post(f"/api/games/{sid}/command", json={"input": "skill"})
    assert r.status_code == 200
    body = r.json()
    # 法师 atk14+12=26 vs def5 → 21 > 普攻 9；MP 100-10=90
    assert body["state"]["battle"]["enemy"]["hp"] == 40 - 21
    assert body["state"]["hero"]["mp"] == 90
    dmg_line = next(m for m in body["messages"] if "伤害" in m)
    assert "21" in dmg_line


def test_battle_win_clears_enemy_and_allows_go(client):
    sid = _new_game(client, cls="rogue")
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    for _ in range(3):
        r = client.post(f"/api/games/{sid}/command", json={"input": "attack"})
        assert r.status_code == 200
    body = r.json()
    # 战斗视图保留但翻转为已结算（前端按 over 隐藏战斗面板）
    assert body["state"]["battle"]["over"] is True
    assert body["state"]["battle"]["result"] == "win"
    assert body["state"]["pending_enemy"] is None
    joined = _msg_join(body["messages"])
    assert "胜利" in joined
    # 清场后可北上
    r = client.post(f"/api/games/{sid}/command", json={"input": "go north"})
    assert r.status_code == 200
    assert r.json()["state"]["scene"]["id"] == "deep_forest"


def test_hero_death_marks_game_over(client):
    sid = _new_game(client, cls="rogue")
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    # 白盒：把英雄压到 1 HP（战斗中败北分支 CLI 由输入流耗尽兜底，网页需显式终局）
    app_state = _app_state(client)
    session = app_state.service.store.get(sid)
    session.hero.hp = 1
    r = client.post(f"/api/games/{sid}/command", json={"input": "attack"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["game_over"] is True
    assert body["state"]["battle"] is not None  # 战斗记录保留供 UI 结算
    assert any("失败" in m for m in body["messages"])
    # 终局后指令一律 400
    r = client.post(f"/api/games/{sid}/command", json={"input": "look"})
    assert r.status_code == 400
    assert "读档" in r.json()["detail"]


def test_skill_downgrades_when_mp_exhausted(client):
    sid = _new_game(client, cls="warrior")
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    app_state = _app_state(client)
    session = app_state.service.store.get(sid)
    session.battle.b.hp = 500
    session.battle.b.max_hp = 500
    for _ in range(3):
        r = client.post(f"/api/games/{sid}/command", json={"input": "skill"})
        assert r.status_code == 200
        assert r.json()["state"]["hero"]["mp"] == 30 - 10 * (_ + 1)
    # 第 4 次：MP 0 → 自动降级为普通攻击
    r = client.post(f"/api/games/{sid}/command", json={"input": "skill"})
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["hero"]["mp"] == 0
    assert any("降级" in m for m in body["messages"])


def _app_state(client):
    return client.app.state


# ---- 存读档 ----


def test_save_and_load_roundtrip(client):
    sid = _new_game(client, cls="mage", name="梅林")
    # 打一场消耗 HP/MP，制造与初始态的差异
    client.post(f"/api/games/{sid}/command", json={"input": "fight"})
    client.post(f"/api/games/{sid}/command", json={"input": "skill"})
    r = client.post(f"/api/games/{sid}/save", json={"slot": "s1"})
    assert r.status_code == 200
    # 继续消耗
    client.post(f"/api/games/{sid}/command", json={"input": "skill"})
    after_more = client.get(f"/api/games/{sid}").json()
    assert after_more["state"]["hero"]["mp"] < 90

    r = client.post(f"/api/games/{sid}/load", json={"slot": "s1"})
    assert r.status_code == 200
    body = r.json()
    hero = body["state"]["hero"]
    assert hero["name"] == "梅林"
    assert hero["mp"] == 90
    assert body["state"]["scene"]["id"] == "forest"
    assert body["state"]["battle"] is None
    assert body["state"]["pending_enemy"]["id"] == "wolf"
    assert body["state"]["game_over"] is False


def test_load_missing_slot_400(client):
    sid = _new_game(client)
    r = client.post(f"/api/games/{sid}/load", json={"slot": "ghost"})
    assert r.status_code == 400
    assert "槽位" in r.json()["detail"]


def test_saves_listing(client):
    sid = _new_game(client)
    client.post(f"/api/games/{sid}/save", json={"slot": "alpha"})
    r = client.get("/api/saves")
    assert r.status_code == 200
    assert "alpha" in r.json()