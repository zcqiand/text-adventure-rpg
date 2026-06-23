# text-adventure-rpg — Claude Code 项目级上下文

> 本文件是《Harness 工程》第 4 章「CLAUDE.md 怎么写」的实物示例。

## 项目定位

文字冒险 RPG 游戏，单进程命令行运行，无外部依赖。用于演示 Claude Code 在中等复杂度项目中的控制平面、多文件协作、上下文治理、错误恢复、持久化等能力。

## 技术栈

- Python 3.10+
- 标准库优先，外部依赖仅 `pytest`（测试）
- 状态以 JSON 持久化到 `~/.text-adventure-rpg/saves/`

## 目录结构

```text
text-adventure-rpg/
├── pyproject.toml
├── CLAUDE.md                      ← 本文件
├── .claude/settings.json          ← 权限与 Hooks 配置（第 5 章）
├── src/text_adventure_rpg/
│   ├── __main__.py                 ← 主循环入口（第 6 章 Agent Loop）
│   ├── engine.py                   ← 控制平面四环节（第 3 章）
│   ├── scenes.py                   ← 场景加载
│   ├── items.py                    ← 物品系统
│   ├── npcs.py                     ← NPC 行为
│   ├── persistence.py              ← 存档读档（第 10 章）
│   └── data/                       ← 场景/物品/NPC 定义 JSON（随包分发）
│       ├── scenes/
│       ├── items/
│       └── npcs/
└── tests/
```

## 编码约定

- **零伪代码**：禁止 `...` 占位、`pass` 占位、`TODO` 占位。每段代码必须可运行。
- **数据驱动**：场景/物品/NPC 必须从 `data/` 加载，禁止硬编码到 Python 文件。
- **错误处理**：所有文件 I/O 必须捕获 `FileNotFoundError` 和 `json.JSONDecodeError`，并给出可读错误信息。
- **存档原子性**：写入存档时先写临时文件再重命名，禁止直接覆盖。

## 危险操作

以下操作需要用户二次确认（已在 `.claude/settings.json` 的 Hooks 中配置）：

- 删除 `~/.text-adventure-rpg/saves/` 下任何存档
- 修改 `data/` 下任何 JSON 文件
- 修改 `engine.py` 的核心战斗循环逻辑

## 测试要求

任何新增功能必须同步加 pytest 测试。提交前必须通过：

```bash
pytest -v
```

## 与本书的关系

| 章节 | 本仓库对应 |
| ---- | ---------- |
| 第 3 章 控制平面 | `engine.py` 的 perceive → plan → act → verify 四步骤 |
| 第 4 章 上下文治理 | 本文件即是示例 |
| 第 5 章 权限/Hooks | `.claude/settings.json` |
| 第 6 章 Agent Loop | `__main__.py` 主循环 |
| 第 8 章 多文件协作 | `scenes.py` + `items.py` + `npcs.py` 三文件同步修改 |
| 第 9 章 错误恢复 | `engine.py` 的回滚/重试/降级分支 |
| 第 10 章 持久化 | `persistence.py` |
