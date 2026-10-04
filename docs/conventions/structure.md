# 目录结构与模块职责

> 从 CLAUDE.md 移出（L0 60 行门）。树是文件系统的复写，以仓库实际为准；
> 模块职责注解在此维护。

```text
text-adventure-rpg/
├── pyproject.toml
├── CLAUDE.md
├── .claude/settings.json
├── src/text_adventure_rpg/
│   ├── __main__.py                 ← 主循环入口（text-rpg）
│   ├── game.py                     ← 战斗集成版入口（text-full-rpg）
│   ├── engine.py                   ← 控制平面四环节
│   ├── scenes.py                   ← 场景加载
│   ├── items.py                    ← 物品系统
│   ├── npcs.py                     ← NPC 行为
│   ├── character.py                ← 角色系统
│   ├── combat.py                   ← 回合制战斗
│   ├── formulas.py                 ← 数值公式
│   ├── narrative.py                ← 动态叙事
│   ├── persistence.py              ← 存档读档
│   ├── validators.py               ← 启动自检
│   └── data/                       ← 场景/物品/NPC 定义 JSON
│       ├── scenes/
│       ├── items/
│       └── npcs/
└── tests/
```
