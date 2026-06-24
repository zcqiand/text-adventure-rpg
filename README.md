# text-adventure-rpg

《Harness 工程：围绕 Claude Code 构建可靠系统》一书**卷一卷二**的可部署案例项目——文字冒险 RPG 游戏。

本仓库是书中讲解 Claude Code 控制平面、Agent Loop、上下文治理、多文件协作、错误恢复、持久化等核心概念的实物载体。

## 章节映射

| 章节 | 对应代码 |
|------|---------|
| 第 1 章 案例介绍 | 仓库整体结构 |
| 第 3 章 控制平面四环节 | `src/text_adventure_rpg/engine.py` |
| 第 4 章 项目级上下文 | `CLAUDE.md` |
| 第 5 章 权限/沙箱/Hooks | `.claude/settings.json` |
| 第 6 章 Agent Loop | `src/text_adventure_rpg/__main__.py` |
| 第 7 章 任务分解 | `src/text_adventure_rpg/engine.py` 中的任务循环 |
| 第 8 章 多文件协作 | `src/text_adventure_rpg/scenes.py` + `items.py` + `npcs.py` |
| 第 9 章 错误恢复 | `src/text_adventure_rpg/engine.py` 的回滚/重试/降级 |
| 第 10 章 持久化 | `src/text_adventure_rpg/persistence.py` |

## xr-know-002《Claude Code 从入门到项目实践》案例扩充（v2.0-002）

本仓库同时作为《Claude Code 从入门到项目实践》(xr-know-002) 卷三（文字冒险 RPG 游戏）的实物载体。卷三第 30-31 章在原 005 模块基础上额外用到以下模块：

| 章节 | 对应代码 |
|------|---------|
| 第 30 章 战斗系统与数值平衡 | `src/text_adventure_rpg/combat.py` + `character.py` + `formulas.py` |
| 第 31 章 动态叙事与 LLM 集成 | `src/text_adventure_rpg/narrative.py`（`client=None` 走本地确定性模板，CI 不依赖 LLM Key） |

其余卷三章（立项架构/场景图/NPC物品/存档测试/调试发布）仍对应原 005 模块（engine/scenes/items/npcs/persistence/validators）。

## 快速开始

```bash
# 安装（需要 Python 3.10+）
pip install -e .

# 运行
text-rpg

# 跑测试
pytest
```

## 部署架构

单进程命令行游戏，无外部依赖。状态以 JSON 文件持久化到 `~/.text-adventure-rpg/saves/`。

```
玩家输入 ──▶ Engine（控制平面）
                │
                ├─ 意图理解 ──▶ Scene 加载
                ├─ 计划制定 ──▶ NPC 行为
                ├─ 执行     ──▶ Item 应用
                └─ 反馈验证 ──▶ State 持久化
```

## 配套书籍

- **书名**：Harness 工程：围绕 Claude Code 构建可靠系统
- **作者**：南荣相如
- **代码片段索引**：[claudecode-harness-book](https://github.com/zcqiand/claudecode-harness-book)
- **Issues**：https://github.com/zcqiand/text-adventure-rpg/issues
