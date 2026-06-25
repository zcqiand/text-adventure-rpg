"""战斗版游戏入口：把 character / formulas / combat / narrative 接入可玩流程。

与 :mod:`__main____` 的「简化战斗」版（直接扣 ``state.player_hp``）并行存在：
本模块用 :class:`character.Character` + :class:`combat.Battle` + :func:`formulas.calc_damage`
做数值驱动的回合制战斗，并用 :class:`narrative.Narrator`（本地降级，零网络）渲染场景文本。

设计取舍：
- **不改 005 在用的模块**：``__main__.py`` / ``engine.py`` / ``scenes`` / ``npcs`` /
  ``items`` / ``persistence`` / ``validators`` 一律只**调用**不改。所以这里**不复用**
  ``persistence.GameState``（它只跟踪 player_hp+inventory，没有职业/MP/atk），而是
  自含一份带 ``battle-`` 前缀的轻量 JSON 存档，与 005 的存档命名空间隔离。
- **数据驱动**：场景沿用 ``data/scenes/``；敌人放在新增的 ``data/enemies/``（NPC 模板
  没有战斗数值 def_，不适合直接当 :class:`Character` 用）。
- **可测优先**：业务逻辑（职业选择、战斗编排、存档序列化）抽成纯函数，``main`` 只做
  IO 编排，测试不必驱动整个 REPL。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Callable, Iterable

from .character import Character, ClassType, make_character
from .combat import Battle
from .formulas import calc_damage, calc_mp_cost
from .narrative import Narrator
from .scenes import Scene, load_scene


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 战斗版存档文件前缀，与 005 的 persistence 槽位命名空间隔离。
BATTLE_SAVE_PREFIX = "battle-"
#: 战斗版存档 schema 版本（独立于 persistence.SCHEMA_VERSION）。
BATTLE_SAVE_SCHEMA_VERSION = 1

#: 技能基础 MP 消耗（公开为模块常量，便于测试断言）。
SKILL_BASE_COST = 10
#: 技能 MP 消耗倍率（公开为模块常量，便于测试断言）。
SKILL_COST_MULTIPLIER = 1.0
#: 技能伤害相对普通攻击的额外加成（一次性高伤，但扣 MP）。
SKILL_BONUS_ATK = 12

#: 选职业菜单。顺序固定保证 ``1/2/3`` 稳定映射。
_CLASS_MENU: list[tuple[str, ClassType, str]] = [
    ("1", ClassType.WARRIOR, "战士（高血量·中等攻击·低法力·肉搏型）"),
    ("2", ClassType.MAGE, "法师（低血量·高法力·依赖技能型）"),
    ("3", ClassType.ROGUE, "盗贼（中血量·高攻击·爆发型）"),
]

#: 每个场景默认遭遇的敌人 id。遇敌机制：进入特定场景时该敌人即出现，
#: 玩家可用 ``fight`` 主动开战；敌人在场时无法 ``go``（与 engine 的「未清场禁移动」
#: 行为一致，但这里走战斗版数据结构）。
#:
#: forest 入口派弱敌 wolf（Lv1）；deep_forest 深处升级为 bandit（Lv2，atk/def 更高），
#: 形成「越往北越危险」的难度梯度。village_gate（南）是安全区，不登记任何敌人。
_SCENE_ENEMIES: dict[str, str] = {
    "forest": "wolf",
    "deep_forest": "bandit",
}


# ---------------------------------------------------------------------------
# 可覆盖的 IO 接缝（测试用 monkeypatch 替换）
# ---------------------------------------------------------------------------

#: 默认就是内建 input；测试可 monkeypatch 成假输入序列。
_prompt: Callable[..., str] = input

#: 默认返回 ``~/.text-adventure-rpg/saves/``；测试 monkeypatch 成 tmp_path。
def _save_dir_override() -> Path | None:
    return None


def _save_dir() -> Path:
    """解析存档目录：优先用 override，否则落回默认 ``~/.text-adventure-rpg/saves/``。"""
    override = _save_dir_override()
    if override is not None:
        return Path(override)
    return Path.home() / ".text-adventure-rpg" / "saves"


def _print(msg: str = "") -> None:
    print(msg)


# ---------------------------------------------------------------------------
# 职业选择（纯函数）
# ---------------------------------------------------------------------------


def choose_class(choice: str, name: str) -> Character | None:
    """把玩家输入的菜单选项解析成对应职业的 Character。

    Args:
        choice: 玩家输入的选项字符串（``"1"`` / ``"2"`` / ``"3"``）。
        name: 角色显示名。

    Returns:
        对应职业的 1 级满血满蓝角色；输入无法识别时返回 ``None``，由调用方决定
        重试还是退出。
    """
    cleaned = (choice or "").strip()
    for key, cls, _desc in _CLASS_MENU:
        if cleaned == key:
            return make_character(name, cls)
    return None


# ---------------------------------------------------------------------------
# 敌人加载（data/enemies/<id>.json → Character）
# ---------------------------------------------------------------------------


def load_enemy(enemy_id: str) -> Character:
    """从包内 ``data/enemies/<id>.json`` 加载敌人成 :class:`Character`。

    与 :func:`npcs.load_npc` 平行：NPC 模板没有战斗数值 ``def_``，不适合直接当
    :class:`Character`，故敌人单独成目录。JSON 字段直接对应 :class:`Character`。

    Raises:
        FileNotFoundError: 找不到对应 JSON 文件。
        ValueError: JSON 解析失败或缺少字段。
    """
    data_root = resources.files("text_adventure_rpg") / "data" / "enemies"
    target = data_root / f"{enemy_id}.json"
    if not target.is_file():
        raise FileNotFoundError(f"未找到敌人定义: {enemy_id}.json")

    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"敌人 {enemy_id} 的 JSON 解析失败: {exc}") from exc

    required = {
        "id", "name", "hp", "max_hp", "mp", "max_mp", "atk", "def_", "level",
        "defeat_message", "victory_message",
    }
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"敌人 {enemy_id} 缺少字段: {sorted(missing)}")

    return Character(
        name=payload["name"],
        hp=int(payload["hp"]),
        max_hp=int(payload["max_hp"]),
        mp=int(payload["mp"]),
        max_mp=int(payload["max_mp"]),
        atk=int(payload["atk"]),
        def_=int(payload["def_"]),
        level=int(payload["level"]),
    )


def _enemy_messages(enemy_id: str) -> tuple[str, str]:
    """读取敌人的胜负文案（load_enemy 不存这些，单独读一次）。"""
    data_root = resources.files("text_adventure_rpg") / "data" / "enemies"
    target = data_root / f"{enemy_id}.json"
    raw = target.read_text(encoding="utf-8")
    payload = json.loads(raw)
    return payload["defeat_message"], payload["victory_message"]


# ---------------------------------------------------------------------------
# 战斗编排（纯函数，返回日志文本；不改 IO）
# ---------------------------------------------------------------------------


def _player_attack(battle: Battle, player: Character, enemy: Character) -> str:
    """玩家普通攻击一回合（含敌人反击），返回日志。"""
    lines: list[str] = []
    dmg = battle.attack(player, enemy)
    lines.append(f"  你对 {enemy.name} 造成 {dmg} 点伤害。（{enemy.name} HP {enemy.hp}/{enemy.max_hp}）")
    if battle.is_over():
        return "\n".join(lines)
    # 敌人反击
    counter = battle.attack(enemy, player)
    lines.append(
        f"  {enemy.name} 反击，对你造成 {counter} 点伤害。（你 HP {player.hp}/{player.max_hp}）"
    )
    return "\n".join(lines)


def _player_skill(battle: Battle, player: Character, enemy: Character) -> str:
    """玩家技能：高伤，扣 MP；MP 不足降级为普通攻击。返回日志。"""
    cost = calc_mp_cost(SKILL_BASE_COST, SKILL_COST_MULTIPLIER)
    if player.mp < cost:
        # 降级提示 + 普通攻击（不扣 MP）
        return (
            f"  （法力不足：需 {cost}，当前 {player.mp}。技能降级为普通攻击。）\n"
            + _player_attack(battle, player, enemy)
        )
    player.mp -= cost
    # 技能伤害 = calc_damage(atk + bonus, def_)
    skill_atk = player.atk + SKILL_BONUS_ATK
    dmg = calc_damage(skill_atk, enemy.def_)
    enemy.take_damage(dmg)
    lines = [
        f"  你施放技能（耗 {cost} MP），对 {enemy.name} 造成 {dmg} 点伤害！"
        f"（{enemy.name} HP {enemy.hp}/{enemy.max_hp}；你 MP {player.mp}/{player.max_mp}）"
    ]
    if battle.is_over():
        return "\n".join(lines)
    counter = battle.attack(enemy, player)
    lines.append(
        f"  {enemy.name} 反击，对你造成 {counter} 点伤害。（你 HP {player.hp}/{player.max_hp}）"
    )
    return "\n".join(lines)


def run_battle(
    battle: Battle,
    player_actions: Iterable[str],
) -> str:
    """驱动一场战斗到结束，返回累积日志。

    每个玩家动作执行后，若战斗未结束，敌人立即反击（``_player_*`` 内联处理）。
    未知动作按普通攻击处理，避免卡死循环。动作序列耗尽而战斗未结束时，
    自动追加普通攻击直到 ``battle.is_over()``，保证函数总是返回终态。

    Args:
        battle: 已用 a=player、b=enemy 构造好的 :class:`Battle`。
        player_actions: 玩家每回合的动作序列（``"attack"`` / ``"skill"`` / 其他）。

    Returns:
        多行战斗日志。
    """
    player, enemy = battle.a, battle.b
    log_lines: list[str] = [f"== 战斗开始：你 vs {enemy.name} =="]

    def _do_action(action: str) -> bool:
        """执行一个动作；返回 True 表示战斗结束。"""
        cleaned = (action or "").strip().lower()
        if cleaned in {"skill", "cast", "magic", "技能"}:
            log_lines.append(_player_skill(battle, player, enemy))
        else:
            # attack / unknown 一律走普通攻击
            log_lines.append(_player_attack(battle, player, enemy))
        return battle.is_over()

    for action in player_actions:
        if battle.is_over():
            break
        if _do_action(action):
            break

    # 兜底：动作耗尽仍未结束，自动普通攻击直到分出胜负（防卡死）
    guard = 0
    while not battle.is_over() and guard < 10000:
        _do_action("attack")
        guard += 1

    winner = battle.winner()
    if winner is player:
        log_lines.append("== 战斗胜利！==")
    elif winner is enemy:
        log_lines.append("== 战斗失败……==")
    else:
        log_lines.append("== 战斗结束（无胜者）==")
    return "\n".join(log_lines)


# ---------------------------------------------------------------------------
# 叙事
# ---------------------------------------------------------------------------


def make_narrator() -> Narrator:
    """构造本地降级叙事器（``client=None``，零网络、确定性）。"""
    return Narrator(client=None)


def _narrate_scene(narrator: Narrator, scene: Scene, hero: Character) -> str:
    """用 Narrator 生成场景进入文本。"""
    return narrator.narrate(
        scene.id,
        {"hero": hero.name, "hp": hero.hp, "scene": scene.name},
    )


# ---------------------------------------------------------------------------
# 存档（自含 JSON，battle- 前缀；不依赖 persistence.GameState）
# ---------------------------------------------------------------------------


def character_to_dict(c: Character, scene_id: str) -> dict:
    """把角色 + 当前场景序列化成存档 payload。"""
    return {
        "schema_version": BATTLE_SAVE_SCHEMA_VERSION,
        "character": {
            "name": c.name,
            "hp": c.hp,
            "max_hp": c.max_hp,
            "mp": c.mp,
            "max_mp": c.max_mp,
            "atk": c.atk,
            "def_": c.def_,
            "level": c.level,
        },
        "current_scene_id": scene_id,
    }


def character_from_dict(payload: dict) -> tuple[Character, str]:
    """从存档 payload 还原 (Character, scene_id)。"""
    version = payload.get("schema_version")
    if version != BATTLE_SAVE_SCHEMA_VERSION:
        raise ValueError(
            f"战斗版存档版本不兼容: 期望 {BATTLE_SAVE_SCHEMA_VERSION}, 实际 {version}"
        )
    ch = payload["character"]
    c = Character(
        name=ch["name"],
        hp=int(ch["hp"]),
        max_hp=int(ch["max_hp"]),
        mp=int(ch["mp"]),
        max_mp=int(ch["max_mp"]),
        atk=int(ch["atk"]),
        def_=int(ch["def_"]),
        level=int(ch["level"]),
    )
    return c, payload["current_scene_id"]


def _slot_path(slot: str, save_dir: Path) -> Path:
    return save_dir / f"{BATTLE_SAVE_PREFIX}{slot}.json"


def save_character(
    c: Character, scene_id: str, slot: str = "default", save_dir: Path | None = None
) -> Path:
    """原子写入战斗版存档（先写 .tmp 再 os.replace）。"""
    target_dir = save_dir or _save_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _slot_path(slot, target_dir)
    payload = character_to_dict(c, scene_id)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        prefix=f".{BATTLE_SAVE_PREFIX}{slot}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)
    return target


def load_character(slot: str = "default", save_dir: Path | None = None) -> tuple[Character, str]:
    """读取战斗版存档，返回 (Character, scene_id)。

    Raises:
        FileNotFoundError: 槽位不存在。
        ValueError: JSON 损坏或版本不兼容。
    """
    target_dir = save_dir or _save_dir()
    target = _slot_path(slot, target_dir)
    if not target.is_file():
        raise FileNotFoundError(f"战斗版存档槽位不存在: {slot}")
    raw = target.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"战斗版存档 {slot} 解析失败: {exc}") from exc
    return character_from_dict(payload)


# ---------------------------------------------------------------------------
# 状态展示
# ---------------------------------------------------------------------------


def render_status(hero: Character, cls: ClassType) -> str:
    """渲染角色状态卡。"""
    return (
        f"== {hero.name}（{cls.value}）状态 ==\n"
        f"  HP {hero.hp}/{hero.max_hp}  MP {hero.mp}/{hero.max_mp}\n"
        f"  ATK {hero.atk}  DEF {hero.def_}  Lv {hero.level}"
    )


# ---------------------------------------------------------------------------
# main：IO 编排
# ---------------------------------------------------------------------------


WELCOME = """
=======================================
   文字冒险 RPG · 战斗版（卷三战斗/职业/数值/叙事集成）
=======================================

本入口把 character / formulas / combat / narrative 四个模块接成可玩流程，
与 `python -m text_adventure_rpg`（005 的 Agent Loop 简化战斗版）并行。

可用指令：
  look                用 Narrator 重渲染当前场景
  go <方向>           移动（遇敌场景未清场则无法离开）
  fight               与当前场景的敌人开战
  attack              战斗中普通攻击
  skill               战斗中施放技能（耗 MP，伤害更高；MP 不足自动降级为攻击）
  status              查看角色 HP/MP/ATK
  save [槽位]         存档（默认槽位 default，文件名 battle-<槽位>.json）
  load <槽位>         读档
  quit                退出
"""


def _prompt_class() -> Character:
    """交互式选职业，直到合法输入。"""
    while True:
        _print("\n请选择职业：")
        for key, _cls, desc in _CLASS_MENU:
            _print(f"  {key}. {desc}")
        try:
            choice = _prompt("\n> ")
        except EOFError:
            # 输入流提前结束：默认战士，保证流程可继续
            choice = "1"
        name = "冒险者"
        hero = choose_class(choice, name)
        if hero is not None:
            _print(f"\n你选择了「{hero.name}」（{_class_value(choice)}）。")
            return hero
        _print("（无效选项，请输入 1 / 2 / 3）")


def _class_value(choice: str) -> str:
    """选项 → 职业中文显示名。"""
    for key, cls, _desc in _CLASS_MENU:
        if choice == key:
            return cls.value
    return "warrior"


def _battle_loop(
    hero: Character, enemy_id: str, narrator: Narrator
) -> tuple[Character, str]:
    """进入并跑完一场战斗，返回 (可能更新后的 hero, 结果文本)。"""
    enemy = load_enemy(enemy_id)
    battle = Battle(hero, enemy)
    _print(narrator.narrate("battle_start", {"hero": hero.name, "enemy": enemy.name}))

    while not battle.is_over():
        try:
            action = _prompt("\n战斗中（attack / skill）> ")
        except EOFError:
            action = "attack"
        cleaned = (action or "").strip().lower() or "attack"

        if cleaned in {"skill", "cast", "magic", "技能"}:
            _print(_player_skill(battle, hero, enemy))
        elif cleaned in {"attack", "a", "攻击", ""}:
            _print(_player_attack(battle, hero, enemy))
        else:
            _print(f"（未识别 {cleaned}，按普通攻击处理）")
            _print(_player_attack(battle, hero, enemy))

    winner = battle.winner()
    defeat_msg, victory_msg = _enemy_messages(enemy_id)
    if winner is hero:
        _print(f"== 战斗胜利！{defeat_msg}")
        _print(narrator.narrate("battle_win", {"hero": hero.name, "enemy": enemy.name}))
        return hero, "win"
    _print(f"== 战斗失败……{victory_msg}")
    _print(narrator.narrate("battle_lose", {"hero": hero.name, "enemy": enemy.name}))
    return hero, "lose"


def main(argv: list[str] | None = None) -> int:
    """战斗版游戏入口。被 console_scripts ``text-full-rpg`` 调用。"""
    _print(WELCOME)

    narrator = make_narrator()
    hero: Character | None = None
    cls: ClassType | None = None
    current_scene: Scene | None = None
    # 当前场景的敌人 id；None 表示该场景无敌人或敌人已被击败。
    pending_enemy: str | None = None

    # 先尝试自动读档提示（与 __main__ 类似的「续上次」体验，但独立命名空间）
    saves_dir = _save_dir()
    existing = (
        [p.stem[len(BATTLE_SAVE_PREFIX):] for p in saves_dir.glob(f"{BATTLE_SAVE_PREFIX}*.json")]
        if saves_dir.is_dir() else []
    )
    start_scene_id = "forest"

    if existing:
        _print(f"发现战斗版存档：{', '.join(existing)}")
        try:
            ans = _prompt("读取哪个？回车跳过开始新游戏 > ").strip()
        except EOFError:
            ans = ""
        if ans:
            try:
                hero, scene_id = load_character(ans)
                current_scene = load_scene(scene_id)
                cls = _infer_class(hero)
                start_scene_id = scene_id
                _print(f"已读取存档 {ans}。")
            except (FileNotFoundError, ValueError) as exc:
                _print(f"读档失败：{exc}。开始新游戏。")

    if hero is None:
        hero = _prompt_class()
        cls = _infer_class(hero)
        current_scene = load_scene(start_scene_id)

    assert hero is not None and current_scene is not None and cls is not None
    pending_enemy = _scene_pending_enemy(current_scene.id)

    # 进入初始场景
    _print(current_scene.on_enter)
    _print(_narrate_scene(narrator, current_scene, hero))

    # ---- 主循环 ----
    while True:
        try:
            raw = _prompt("\n> ")
        except (EOFError, KeyboardInterrupt):
            _print()
            break

        cleaned = (raw or "").strip().lower()
        if not cleaned:
            continue

        # 元指令分流（不进战斗）
        if cleaned in {"quit", "exit", ":q"}:
            _print("再见，冒险者。")
            break

        if cleaned == "status":
            _print(render_status(hero, cls))
            continue

        if cleaned in {"look", "l"}:
            _print(_narrate_scene(narrator, current_scene, hero))
            continue

        if cleaned == "save" or cleaned.startswith("save "):
            slot = cleaned[5:].strip() if cleaned.startswith("save ") else "default"
            if not slot:
                slot = "default"
            try:
                path = save_character(hero, current_scene.id, slot=slot)
            except OSError as exc:
                _print(f"(存档失败: {exc})")
                continue
            _print(f"(已存档到 {path})")
            continue

        if cleaned.startswith("load "):
            target_slot = cleaned[5:].strip()
            try:
                loaded_hero, loaded_scene_id = load_character(target_slot)
            except (FileNotFoundError, ValueError) as exc:
                _print(f"(读档失败: {exc})")
                continue
            hero = loaded_hero
            cls = _infer_class(hero)
            current_scene = load_scene(loaded_scene_id)
            pending_enemy = _scene_pending_enemy(current_scene.id)
            _print(f"(已读取存档 {target_slot})")
            _print(_narrate_scene(narrator, current_scene, hero))
            continue

        # 移动
        if cleaned.startswith("go ") or cleaned in current_scene.exits:
            direction = cleaned[3:].strip() if cleaned.startswith("go ") else cleaned
            if direction not in current_scene.exits:
                _print(f"你无法朝「{direction}」前进。")
                continue
            if pending_enemy is not None:
                _print(f"敌人挡住了你的路（{pending_enemy}）。先 fight 解决它。")
                continue
            target_id = current_scene.exits[direction]
            try:
                current_scene = load_scene(target_id)
            except FileNotFoundError:
                _print(f"前方一片虚无（场景 {target_id} 尚未实装）。")
                continue
            pending_enemy = _scene_pending_enemy(current_scene.id)
            _print(current_scene.on_enter)
            _print(_narrate_scene(narrator, current_scene, hero))
            continue

        # 战斗
        if cleaned in {"fight", "attack", "f"} and pending_enemy is not None:
            hero, result = _battle_loop(hero, pending_enemy, narrator)
            if result == "win":
                pending_enemy = None  # 清场
            else:
                # 玩家败：结束游戏
                break
            continue

        if cleaned in {"fight", "attack", "f"}:
            _print("（这里没有敌人可战。）")
            continue

        _print(f"未识别指令: {cleaned}")

    _print(f"（存档目录：{_save_dir()}）")
    return 0


def _infer_class(hero: Character) -> ClassType:
    """根据角色属性反推职业（存档不带职业枚举，按属性表匹配）。

    匹配不到时回退到 WARRIOR（不影响存档/读档的核心字段还原，仅影响显示）。
    """
    for cls in ClassType:
        template = make_character("_", cls)
        if (
            hero.max_hp == template.max_hp
            and hero.max_mp == template.max_mp
            and hero.atk == template.atk
            and hero.def_ == template.def_
        ):
            return cls
    return ClassType.WARRIOR


def _scene_pending_enemy(scene_id: str) -> str | None:
    """查询某场景当前是否挂敌人（每次进场景都重新生成一份）。"""
    return _SCENE_ENEMIES.get(scene_id)


if __name__ == "__main__":
    raise SystemExit(main())
