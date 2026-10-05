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
│   ├── config.py                   ← Web 层 Settings + fail-fast 加载
│   ├── llm_client.py               ← OpenAI 兼容叙事后端（urllib，剥 <think>）
│   ├── game_service.py             ← 战斗版 Web 状态机（会话存储/指令分流/存读档）
│   ├── main.py                     ← create_app 工厂
│   ├── webserver.py                ← uvicorn 入口（text-rpg-web）
│   ├── api/                        ← FastAPI 路由（/api）
│   │   ├── __init__.py
│   │   └── routes.py
│   └── data/                       ← 场景/物品/NPC 定义 JSON
│       ├── scenes/
│       ├── items/
│       └── npcs/
├── frontend/                       ← React 18 + Vite + TS（战斗版 Web 化）
│   ├── vite.config.ts              ← dev 5805，/api 代理到 8805
│   └── src/
│       ├── api.ts                  ← 纯 REST 请求层（同源相对 /api）
│       ├── types.ts                ← 与后端响应形状一一对应
│       ├── App.tsx
│       └── pages/Play.tsx          ← 建局/探索/战斗/终局三态主组件
└── tests/
```
