"""战斗版 Web 服务层：把 game.py 的 REPL 指令分流移植成可注入状态机。

与 CLI（``game.main``）的分工：CLI 是「input() 驱动的 while 循环」，这里是
「一条指令一次调用」的会话状态机——业务核全部复用 game.py 的现成纯函数
（``make_character`` / ``load_enemy`` / ``Battle`` / ``_player_attack`` /
``_player_skill`` / ``save_character`` / ``load_character``），本模块只做
编排与响应组装，不复制任何数值/战斗逻辑。

响应形状呼应 ``engine.TurnResult`` 的「事件 + 状态」分离：每条指令返回
``messages``（本回合发生了什么）与 ``state``（权威状态快照），前端照此渲染。
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import game
from .character import Character, ClassType, make_character
from .combat import Battle
from .items import load_item
from .narrative import Narrator
from .npcs import load_npc
from .scenes import Scene, load_scene

#: 消息日志上限——防长团差旅把内存吃穿；超出丢最旧的。
_LOG_LIMIT = 200


class UnknownSessionError(KeyError):
    """会话不存在。"""


class InvalidInputError(ValueError):
    """非法输入（职业/场景/指令/槽位）。"""


class GameOverError(RuntimeError):
    """会话已终局，只允许读档或开新局。"""


@dataclass
class GameSession:
    """一局进行中的战斗版冒险。"""

    id: str
    created_at: str
    hero: Character
    class_type: ClassType
    scene: Scene
    pending_enemy_id: str | None
    battle: Battle | None = None
    battle_log: list[str] = field(default_factory=list)
    messages_log: list[str] = field(default_factory=list)
    narration: str = ""
    game_over: bool = False


class GameStore:
    """内存会话库（demo 性质，重启即清——ai-tutoring 家族同款取舍）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, GameSession] = {}

    def add(self, session: GameSession) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def get(self, sid: str) -> GameSession | None:
        with self._lock:
            return self._sessions.get(sid)

    def all_newest_first(self) -> list[GameSession]:
        with self._lock:
            return list(reversed(self._sessions.values()))


class GameService:
    """对外用例层：建局、指令、存读档。

    Args:
        saves_dir: battle- 存档目录；``None`` 落回 game.py 默认（~/.text-adventure-rpg/saves）。
        narrator: 叙事器——mock 传 ``Narrator(client=None)``（确定性），live 传
            持 ``OpenAICompatNarrator`` 的 :class:`Narrator`。
    """

    def __init__(self, saves_dir: Path | None, narrator: Narrator) -> None:
        self.store = GameStore()
        self._saves_dir = saves_dir
        self._narrator = narrator

    # ------------------------------------------------------------------
    # 建局
    # ------------------------------------------------------------------

    def create(self, class_key: str, name: str = "冒险者", scene_id: str = "forest") -> GameSession:
        """创建一局新冒险：选职业 + 落入初始场景。"""
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise InvalidInputError("角色名字不能为空")
        try:
            cls = ClassType((class_key or "").strip().lower())
        except ValueError as exc:
            raise InvalidInputError(
                f"无效职业: {class_key!r}，可选 warrior / mage / rogue"
            ) from exc
        hero = make_character(cleaned_name, cls)
        try:
            scene = load_scene(scene_id)
        except FileNotFoundError as exc:
            raise InvalidInputError(f"场景不存在: {scene_id}") from exc

        session = GameSession(
            id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            hero=hero,
            class_type=cls,
            scene=scene,
            pending_enemy_id=game._scene_pending_enemy(scene.id),
        )
        entry = [scene.on_enter, self._narrate_entry(session)]
        session.narration = entry[-1]
        session.messages_log.extend(entry)
        self.store.add(session)
        return session

    # ------------------------------------------------------------------
    # 指令
    # ------------------------------------------------------------------

    def command(self, sid: str, raw: str) -> list[str]:
        """执行一条玩家指令，返回本回合的 messages（状态用 :meth:`view` 另取）。"""
        session = self._require(sid)
        if session.game_over:
            raise GameOverError("冒险已经结束。POST /api/games/{id}/load 读档，或开新局。")
        cleaned = (raw or "").strip().lower()
        if not cleaned:
            raise InvalidInputError("空指令")

        battle_active = session.battle is not None and not session.battle.is_over()
        if battle_active:
            return self._battle_command(session, cleaned)
        return self._explore_command(session, cleaned)

    def _explore_command(self, session: GameSession, cleaned: str) -> list[str]:
        scene = session.scene
        hero = session.hero

        if cleaned in {"look", "l"}:
            messages = [self._narrate_entry(session)]
            session.narration = messages[-1]
            self._log(session, messages)
            return messages

        if cleaned == "status":
            messages = [game.render_status(hero, session.class_type)]
            self._log(session, messages)
            return messages

        if cleaned in {"fight", "f", "attack"}:
            # fight 与 attack 在探索态都是「开战」（CLI 同语义）
            return self._fight(session)

        if cleaned.startswith("go "):
            direction = cleaned[3:].strip()
        elif cleaned in scene.exits:
            direction = cleaned  # 方向词简写，与 CLI 一致
        else:
            messages = [f"未识别指令: {cleaned}"]
            self._log(session, messages)
            return messages

        return self._go(session, direction)

    def _go(self, session: GameSession, direction: str) -> list[str]:
        scene = session.scene
        if direction not in scene.exits:
            messages = [f"你无法朝「{direction}」前进。"]
            self._log(session, messages)
            return messages
        if session.pending_enemy_id is not None:
            enemy_name = self._enemy_name(session.pending_enemy_id)
            messages = [f"{enemy_name} 挡住了你的路。先 fight 解决它。"]
            self._log(session, messages)
            return messages

        target_id = scene.exits[direction]
        try:
            session.scene = load_scene(target_id)
        except FileNotFoundError:
            messages = [f"前方一片虚无（场景 {target_id} 尚未实装）。"]
            self._log(session, messages)
            return messages

        session.pending_enemy_id = game._scene_pending_enemy(target_id)
        entry = [session.scene.on_enter, self._narrate_entry(session)]
        session.narration = entry[-1]
        self._log(session, entry)
        return entry

    def _fight(self, session: GameSession) -> list[str]:
        if session.pending_enemy_id is None:
            return self._log(session, ["（这里没有敌人可战。）"])
        enemy = game.load_enemy(session.pending_enemy_id)
        session.battle = Battle(session.hero, enemy)
        session.battle_log = [f"== 战斗开始：{session.hero.name} vs {enemy.name} =="]
        intro = [
            self._narrator.narrate(
                "battle_start", {"hero": session.hero.name, "enemy": enemy.name}
            ),
            f"{enemy.name} 出现在你面前！（HP {enemy.hp}/{enemy.max_hp}）",
            "战斗中：attack 普通攻击 / skill 施放技能（耗 MP，MP 不足自动降级）。",
        ]
        self._log(session, intro)
        return intro

    # ------------------------------------------------------------------
    # 战斗回合
    # ------------------------------------------------------------------

    def _battle_command(self, session: GameSession, cleaned: str) -> list[str]:
        enemy = session.battle.b
        if cleaned in {"skill", "cast", "magic", "技能"}:
            turn = game._player_skill(session.battle, session.hero, enemy)
        elif cleaned in {"attack", "a", "攻击", "f"}:
            turn = game._player_attack(session.battle, session.hero, enemy)
        else:
            raise InvalidInputError("战斗中只接受 attack / skill")
        session.battle_log.append(turn)

        messages = [turn]
        if session.battle.is_over():
            messages.extend(self._settle_battle(session))
        self._log(session, messages)
        return messages

    def _settle_battle(self, session: GameSession) -> list[str]:
        """战斗分出胜负后的收尾：清场/终局/叙事，返回追加消息。"""
        enemy = session.battle.b
        defeat_msg, victory_msg = game._enemy_messages(session.pending_enemy_id)
        if session.battle.winner() is session.hero:
            session.pending_enemy_id = None
            tail = [
                f"== 战斗胜利！{defeat_msg}",
                self._narrator.narrate(
                    "battle_win", {"hero": session.hero.name, "enemy": enemy.name}
                ),
            ]
        else:
            session.game_over = True
            tail = [
                f"== 战斗失败……{victory_msg}",
                self._narrator.narrate(
                    "battle_lose", {"hero": session.hero.name, "enemy": enemy.name}
                ),
            ]
        session.battle_log.extend(tail)
        return tail

    # ------------------------------------------------------------------
    # 存读档
    # ------------------------------------------------------------------

    def save(self, sid: str, slot: str) -> dict:
        """存档到 battle-<slot>.json（原子写，复用 game.save_character）。"""
        session = self._require(sid)
        cleaned = (slot or "").strip()
        if not cleaned:
            raise InvalidInputError("槽位名不能为空")
        try:
            game.save_character(session.hero, session.scene.id, slot=cleaned, save_dir=self._resolve_saves_dir())
        except OSError as exc:
            raise InvalidInputError(f"存档失败: {exc}") from exc
        return {"slot": cleaned, "message": f"已存档到槽位 {cleaned}"}

    def load(self, sid: str, slot: str) -> list[str]:
        """从槽位读档并原地重置会话（battle 存档只含 hero + scene_id）。"""
        session = self._require(sid)
        cleaned = (slot or "").strip()
        if not cleaned:
            raise InvalidInputError("槽位名不能为空")
        try:
            hero, scene_id = game.load_character(cleaned, save_dir=self._resolve_saves_dir())
            scene = load_scene(scene_id)
        except (FileNotFoundError, ValueError) as exc:
            raise InvalidInputError(f"槽位 {cleaned} 不可用：{exc}") from exc

        session.hero = hero
        session.class_type = game._infer_class(hero)
        session.scene = scene
        session.pending_enemy_id = game._scene_pending_enemy(scene_id)
        session.battle = None
        session.battle_log = []
        session.game_over = False
        entry = [f"（已读取存档 {cleaned}）", scene.on_enter, self._narrate_entry(session)]
        session.narration = entry[-1]
        session.messages_log = []
        self._log(session, entry)
        return entry

    def list_saves(self) -> list[str]:
        """列出 battle- 前缀存档槽位（与 005 persistence 槽位命名空间隔离）。"""
        saves_dir = self._resolve_saves_dir()
        if not saves_dir.is_dir():
            return []
        return sorted(
            p.stem[len(game.BATTLE_SAVE_PREFIX):]
            for p in saves_dir.glob(f"{game.BATTLE_SAVE_PREFIX}*.json")
        )

    # ------------------------------------------------------------------
    # 视图
    # ------------------------------------------------------------------

    def view(self, session: GameSession) -> dict:
        """权威状态快照——「事件 + 状态」分离里的 state 半边。"""
        hero = session.hero
        enemy_id = session.pending_enemy_id
        battle_view: dict | None = None
        if session.battle is not None:
            enemy = session.battle.b
            winner = session.battle.winner()
            battle_view = {
                "enemy": {
                    "id": enemy_id,
                    "name": enemy.name,
                    "hp": enemy.hp,
                    "max_hp": enemy.max_hp,
                },
                "log": list(session.battle_log),
                "over": session.battle.is_over(),
                "result": ("win" if winner is session.hero else "lose") if winner else None,
            }
        return {
            "hero": {
                "name": hero.name,
                "class": session.class_type.value,
                "hp": hero.hp,
                "max_hp": hero.max_hp,
                "mp": hero.mp,
                "max_mp": hero.max_mp,
                "atk": hero.atk,
                "def_": hero.def_,
                "level": hero.level,
            },
            "scene": {
                "id": session.scene.id,
                "name": session.scene.name,
                "description": session.scene.description,
                "exits": dict(session.scene.exits),
                "items": [self._item_name(i) for i in session.scene.items],
                "npcs": [self._npc_name(n) for n in session.scene.npcs],
            },
            "pending_enemy": (
                {"id": enemy_id, "name": self._enemy_name(enemy_id)} if enemy_id else None
            ),
            "battle": battle_view,
            "narration": session.narration,
            "log": list(session.messages_log),
            "game_over": session.game_over,
        }

    def summary(self, session: GameSession) -> dict:
        """列表条目：只露少量字段。"""
        return {
            "id": session.id,
            "name": session.hero.name,
            "class": session.class_type.value,
            "level": session.hero.level,
            "hp": session.hero.hp,
            "max_hp": session.hero.max_hp,
            "scene": session.scene.id,
            "created_at": session.created_at,
            "game_over": session.game_over,
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _require(self, sid: str) -> GameSession:
        session = self.store.get(sid)
        if session is None:
            raise UnknownSessionError(sid)
        return session

    def _narrate_entry(self, session: GameSession) -> str:
        return self._narrator.narrate(
            session.scene.id,
            {"hero": session.hero.name, "hp": session.hero.hp, "scene": session.scene.name},
        )

    def _enemy_name(self, enemy_id: str) -> str:
        try:
            return game.load_enemy(enemy_id).name
        except (FileNotFoundError, ValueError):
            return enemy_id

    def _item_name(self, item_id: str) -> str:
        try:
            return load_item(item_id).name
        except (FileNotFoundError, ValueError):
            return item_id

    def _npc_name(self, npc_id: str) -> str:
        try:
            return load_npc(npc_id).name
        except (FileNotFoundError, ValueError):
            return npc_id

    def _resolve_saves_dir(self) -> Path:
        return self._saves_dir if self._saves_dir is not None else game._save_dir()

    def _log(self, session: GameSession, messages: list[str]) -> list[str]:
        session.messages_log.extend(messages)
        if len(session.messages_log) > _LOG_LIMIT:
            session.messages_log = session.messages_log[-_LOG_LIMIT:]
        return messages
