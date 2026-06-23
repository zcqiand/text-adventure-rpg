"""游戏引擎：控制平面四环节 + Agent Loop 演示物。

这是第 3 章「控制平面」和第 6 章「Agent Loop」的实物：

    perceive  ──▶  plan  ──▶  act  ──▶  verify
        ▲                                    │
        └────────────────────────────────────┘

把这四步显式拆开成方法，是为了让书里能直接对照讲解；生产级代码可以
合并优化，但教学代码以「可读性 > 简洁性」为第一优先。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .items import Item, load_item
from .npcs import Npc, NpcState, load_npc
from .persistence import GameState
from .scenes import Scene, load_scene


# 玩家级 undo 栈深度上限——避免无限增长。这个数字大致够「打错一次方向」
# 「拿错一个物品」「不小心攻击错目标」三种最常见后悔情境。
_UNDO_HISTORY_LIMIT = 10


@dataclass
class TurnResult:
    """一回合的输出。

    把日志（messages）与状态变化分开，UI 层可以单独消费——第 13 章在 React
    前端会用到这种「事件 + 状态」分离的回报格式。
    """

    messages: list[str] = field(default_factory=list)
    quit: bool = False


@dataclass
class _EngineSnapshot:
    """一个 turn 开头的可逆状态快照。

    只快照「玩家级可见的可逆状态」——GameState、当前场景 id、NPC 运行期 HP；
    不快照 Scene 模板对象本身（场景定义文件不可变）也不快照已经做过的日志输出。

    这是给玩家用的 undo，不是给开发者用的 /rewind——所以"开发者层"的状态
    （Claude Code session、对话历史）完全不在快照范围内，这与第 9 章反模式
    告诫的"用 Python 模拟 checkpoint"是两件不同的事。
    """

    state: GameState
    current_scene_id: str
    npc_hp_by_id: dict[str, int]
    scene_items: tuple[str, ...]


@dataclass
class Engine:
    """游戏运行期容器。

    持有：
    - 玩家状态（state）
    - 当前场景（current_scene）
    - 当前场景的 NPC 运行期副本（npc_states，按 id 索引）
    - 玩家级 undo 历史栈（_history，玩家可输入 'undo' 回退一步）
    """

    state: GameState
    current_scene: Scene
    npc_states: dict[str, NpcState] = field(default_factory=dict)
    _history: list[_EngineSnapshot] = field(default_factory=list)

    @classmethod
    def new_game(cls, scene_id: str = "forest") -> "Engine":
        """从零开始一局新游戏。"""
        scene = load_scene(scene_id)
        engine = cls(
            state=GameState(
                current_scene_id=scene.id,
                player_hp=30,
                inventory=[],
            ),
            current_scene=scene,
        )
        engine._spawn_scene_npcs()
        return engine

    @classmethod
    def resume(cls, state: GameState) -> "Engine":
        """从存档恢复一局游戏。"""
        scene = load_scene(state.current_scene_id)
        engine = cls(state=state, current_scene=scene)
        engine._spawn_scene_npcs()
        return engine

    def _spawn_scene_npcs(self) -> None:
        """加载当前场景的所有 NPC 到 npc_states。"""
        self.npc_states = {}
        for npc_id in self.current_scene.npcs:
            template = load_npc(npc_id)
            self.npc_states[npc_id] = NpcState.from_template(template)

    # ------------------------------------------------------------------
    # 控制平面四环节
    # ------------------------------------------------------------------

    def perceive(self) -> str:
        """环节 1：意图理解之前，先把环境信息整理成文本展示给玩家。"""
        lines = [
            f"== {self.current_scene.name} ==",
            self.current_scene.description,
        ]
        if self.npc_states:
            alive = [s.template.name for s in self.npc_states.values() if not s.is_dead]
            if alive:
                lines.append("你看到：" + "、".join(alive))
        if self.current_scene.items:
            items = [load_item(i).name for i in self.current_scene.items]
            lines.append("地上有：" + "、".join(items))
        lines.append("可去方向：" + "、".join(self.current_scene.exits.keys()))
        lines.append(f"[HP {self.state.player_hp}]")
        return "\n".join(lines)

    def plan(self, raw_input: str) -> tuple[str, str]:
        """环节 2：把玩家输入解析成 (动作, 参数)。

        极简意图分类器——书中第 7 章会演示如何把这一步换成 LLM 调用，
        到时只需替换这一个方法，外层循环不动。
        """
        cleaned = raw_input.strip().lower()
        if not cleaned:
            return ("noop", "")
        if cleaned in {"quit", "exit", ":q"}:
            return ("quit", "")
        if cleaned in {"undo", "u"}:
            return ("undo", "")
        if cleaned in {"save"}:
            return ("save", "default")
        if cleaned.startswith("save "):
            return ("save", cleaned[5:].strip())
        if cleaned in {"look", "l"}:
            return ("look", "")
        if cleaned.startswith("go "):
            return ("go", cleaned[3:].strip())
        if cleaned in self.current_scene.exits:
            # 允许直接输入方向词作为 go 的简写
            return ("go", cleaned)
        if cleaned.startswith("attack "):
            return ("attack", cleaned[7:].strip())
        if cleaned == "attack" and len(self.npc_states) == 1:
            # 单一目标时无歧义
            target = next(iter(self.npc_states))
            return ("attack", target)
        if cleaned.startswith("take "):
            return ("take", cleaned[5:].strip())
        return ("unknown", cleaned)

    def act(self, action: str, argument: str) -> TurnResult:
        """环节 3：执行动作。

        每个动作都返回 TurnResult，避免静默修改状态——便于第 9 章
        「错误恢复」演示「执行失败时不污染状态」。

        改状态的动作（go / attack / take）在真正执行前先压入 undo 快照；
        不改状态的动作（look / quit / noop / save / undo 本身）不压栈，
        避免污染 undo 历史。
        """
        result = TurnResult()

        if action == "quit":
            result.messages.append("再见，冒险者。")
            result.quit = True
            return result

        if action == "noop":
            result.messages.append("(没听清你说什么)")
            return result

        if action == "look":
            result.messages.append(self.perceive())
            return result

        if action == "undo":
            return self._act_undo(result)

        if action == "go":
            self._snapshot()
            return self._act_go(argument, result)

        if action == "attack":
            self._snapshot()
            return self._act_attack(argument, result)

        if action == "take":
            self._snapshot()
            return self._act_take(argument, result)

        if action == "save":
            # 存档落到调用层处理，引擎只生成提示
            result.messages.append(f"(存档将写入槽位: {argument})")
            return result

        result.messages.append(f"不认识的指令: {argument or action}")
        return result

    def verify(self, before_hp: int) -> list[str]:
        """环节 4：执行后的状态校验与回报。

        当前只做一件事：玩家 HP 归零 → 宣布失败。生产级代码这里还会做
        不变量检查（如背包容量、场景 id 是否在合法集合等）。
        """
        notes: list[str] = []
        if self.state.player_hp <= 0 and before_hp > 0:
            notes.append("== 你倒在了血泊里。游戏结束。==")
        return notes

    # ------------------------------------------------------------------
    # 动作实现
    # ------------------------------------------------------------------

    def _act_go(self, direction: str, result: TurnResult) -> TurnResult:
        if direction not in self.current_scene.exits:
            result.messages.append(f"你无法朝「{direction}」前进。")
            return result

        # 阻止离开未清场的敌对场景——第 7 章会用这个演示「前置条件」
        alive_npcs = [s for s in self.npc_states.values() if not s.is_dead]
        if alive_npcs:
            names = "、".join(s.template.name for s in alive_npcs)
            result.messages.append(f"{names} 挡住了你的路。先解决它们。")
            return result

        target_id = self.current_scene.exits[direction]
        try:
            self.current_scene = load_scene(target_id)
        except FileNotFoundError:
            # 场景文件缺失：第 9 章「错误恢复」会演示降级——这里给出
            # 玩家可读的失败信息，不让程序崩溃
            result.messages.append(f"前方一片虚无（场景 {target_id} 尚未实装）。")
            return result

        self.state.current_scene_id = target_id
        self._spawn_scene_npcs()
        result.messages.append(self.current_scene.on_enter)
        result.messages.append(self.perceive())
        return result

    def _act_attack(self, target_id: str, result: TurnResult) -> TurnResult:
        if target_id not in self.npc_states:
            result.messages.append(f"这里没有「{target_id}」可以攻击。")
            return result

        npc_state = self.npc_states[target_id]
        if npc_state.is_dead:
            result.messages.append(f"{npc_state.template.name} 已经倒下了。")
            return result

        # 玩家造成的伤害：有剑 8 点，徒手 2 点
        player_attack = 2
        for item_id in self.state.inventory:
            try:
                item = load_item(item_id)
            except (FileNotFoundError, ValueError):
                continue
            if item.type == "weapon":
                player_attack = max(player_attack, item.attack)
                break

        dealt = npc_state.take_damage(player_attack)
        result.messages.append(
            f"你对 {npc_state.template.name} 造成 {dealt} 点伤害。"
        )

        if npc_state.is_dead:
            result.messages.append(npc_state.template.defeat_message)
            return result

        # NPC 反击
        counter = npc_state.template.attack
        self.state.player_hp = max(0, self.state.player_hp - counter)
        result.messages.append(
            f"{npc_state.template.name} 反击，对你造成 {counter} 点伤害。"
        )
        if self.state.player_hp <= 0:
            result.messages.append(npc_state.template.victory_message)
        return result

    def _act_take(self, item_id: str, result: TurnResult) -> TurnResult:
        if item_id not in self.current_scene.items:
            result.messages.append(f"这里没有「{item_id}」可以拿取。")
            return result

        try:
            item = load_item(item_id)
        except (FileNotFoundError, ValueError) as exc:
            # 数据契约错误对玩家不可见，但要记下来便于第 9 章演示日志策略
            result.messages.append(f"(无法拿取 {item_id}: {exc})")
            return result

        self.state.inventory.append(item.id)
        # 从场景的物品列表里移除（Scene 是 frozen 的，重新构造）
        new_items = tuple(i for i in self.current_scene.items if i != item_id)
        self.current_scene = Scene(
            id=self.current_scene.id,
            name=self.current_scene.name,
            description=self.current_scene.description,
            exits=self.current_scene.exits,
            items=new_items,
            npcs=self.current_scene.npcs,
            on_enter=self.current_scene.on_enter,
        )
        result.messages.append(f"你拾起了 {item.name}。{item.use_message}")
        return result

    # ------------------------------------------------------------------
    # 玩家级 undo（不是开发者级 /rewind）
    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        """把当前可逆状态压入 undo 栈。

        在每个会改状态的动作（go / attack / take）真正执行之前调用一次。
        如果动作本身没有改任何状态（比如 attack 一个已死的 NPC），栈里
        会留下一个与当前状态等价的快照——这不影响功能，玩家 undo 一次
        就回到等价状态，再 undo 一次回到真正想退回的状态。这种「冗余但
        不出错」的取舍比「检测状态是否真的变了」更简单也更可靠。

        使用 copy.deepcopy 是因为 GameState.inventory 是 list、
        NpcState.current_hp 是 int 但 npc_states 字典本身可变。deepcopy
        统一处理，避免某个字段意外漏拷贝。
        """
        snapshot = _EngineSnapshot(
            state=copy.deepcopy(self.state),
            current_scene_id=self.current_scene.id,
            npc_hp_by_id={
                npc_id: npc_state.current_hp
                for npc_id, npc_state in self.npc_states.items()
            },
            scene_items=self.current_scene.items,
        )
        self._history.append(snapshot)
        # 限制栈深度——这是玩家级 undo，不需要无限历史
        if len(self._history) > _UNDO_HISTORY_LIMIT:
            self._history.pop(0)

    def _act_undo(self, result: TurnResult) -> TurnResult:
        """弹出最近一个快照并恢复。"""
        if not self._history:
            result.messages.append("没有可撤销的动作。")
            return result

        snapshot = self._history.pop()
        self._restore_snapshot(snapshot)
        result.messages.append("已撤销上一个动作。")
        result.messages.append(self.perceive())
        return result

    def _restore_snapshot(self, snapshot: _EngineSnapshot) -> None:
        """按快照恢复玩家状态、场景、NPC 血量。"""
        self.state = snapshot.state

        # 场景如果变了，要重新 load_scene 与 _spawn_scene_npcs
        if self.current_scene.id != snapshot.current_scene_id:
            self.current_scene = load_scene(snapshot.current_scene_id)
            self._spawn_scene_npcs()

        # 场景内物品列表回退（玩家可能拿走了 sword 又 undo）
        if self.current_scene.items != snapshot.scene_items:
            self.current_scene = Scene(
                id=self.current_scene.id,
                name=self.current_scene.name,
                description=self.current_scene.description,
                exits=self.current_scene.exits,
                items=snapshot.scene_items,
                npcs=self.current_scene.npcs,
                on_enter=self.current_scene.on_enter,
            )

        # NPC 血量按 snapshot 恢复（玩家可能砍了哥布林 8 点又 undo）
        for npc_id, npc_state in self.npc_states.items():
            if npc_id in snapshot.npc_hp_by_id:
                npc_state.current_hp = snapshot.npc_hp_by_id[npc_id]
