# text-adventure-rpg

> 单进程、零外部依赖的命令行文字冒险 RPG——两本 Claude Code 实战书的可部署配套案例。

一款纯 Python 标准库实现的文字冒险 RPG 游戏：玩家用文本指令在场景间探索、与敌人回合制战斗、拾取物品、多槽位存档读档。它同时是**两本** Claude Code 实战书的配套代码——书里讲的每一个核心概念（控制平面、Agent Loop、上下文治理、多文件协作、错误恢复、持久化、战斗数值、LLM 叙事……），在本仓库里都有对应的、可运行的最小实现，而不是停在截图或伪代码。

## 项目背景

为什么用一款「游戏」来配书？文字冒险 RPG 的复杂度刚好够用：

- **小而可跑**：零运行时第三方依赖，`pip install -e .` 后立即可玩，读者一次能读完整个仓库；
- **要素齐全**：状态机（场景 / NPC / 物品 / 玩家血量）、控制平面（perceive → plan → act → verify）、持久化（存档）、错误恢复（undo / 降级）、数据契约（多文件一致性校验）、数值系统（伤害公式 / 法力消耗 / 职业差异化）一应俱全；
- **可分可合**：核心探索版讲工程骨架，战斗职业版讲数值与外部集成，两套需求共用同一份场景数据，互不打架。

正是这种「中等复杂度 + 要素全覆盖」的特性，让同一套代码能同时承载两本书的演示而不重样。

## 包含内容

仓库提供**两个并行入口**，分属两本书：

| 入口命令          | 入口模块                                                                | 定位                                                                  | 对应配套书 |
| ----------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------- |
| `text-rpg`      | `__main__.py` + `engine.py`                                         | 核心探索版：perceive→plan→act→verify 主循环，简化战斗（直接扣 HP） | 书一       |
| `text-full-rpg` | `game.py` + `character` / `combat` / `formulas` / `narrative` | 战斗集成版：三职业 + 数值公式 + 回合制战斗 + 叙事渲染                 | 书二       |

两个入口共享同一套场景数据，存档命名空间相互隔离（核心版 `<slot>.json` / 战斗版 `battle-<slot>.json`），可各自独立运行。

## 功能特性

### 游戏玩法

- 场景探索：`go <方向>` / `look`，敌人在场时无法离开
- 回合制战斗：普通攻击 + 技能（耗 MP、伤害更高；MP 不足自动降级为普通攻击）
- 三职业：战士（高血肉搏）/ 法师（高蓝技能型）/ 盗贼（高攻爆发），初始数值刻意拉开差距
- 物品系统：`take` 拾取，武器提升攻击力
- 存档：手动多槽位 `save` / `load` + 每 5 个有效回合自动 `auto-checkpoint`（环形保留最近 3 份）
- 撤销：`undo` 玩家级回退最近 10 步
- 动态叙事：可选接入 LLM 渲染场景文本，默认走本地确定性模板（零网络、CI 不依赖 Key）

### 工程特性（教学要点）

- 控制平面四环节显式拆分，便于书中对照讲解
- 数据驱动：场景 / 物品 / NPC / 敌人全部走 `data/` 下的 JSON，零硬编码
- 启动自检：多文件一致性校验，errors 阻断启动、warnings 放行
- 原子写存档（先写临时文件再 `os.replace`）+ `schema_version` 字段，便于未来格式迁移
- 依赖注入的叙事后端（`NarrationClient` Protocol），外部 LLM 与本地降级可互换

## 章节映射

### 书一《Harness 工程：围绕 Claude Code 构建可靠系统》（卷一·卷二，核心篇）

| 章节                    | 对应代码                                                          |
| ----------------------- | ----------------------------------------------------------------- |
| 第 1 章 案例介绍        | 仓库整体结构                                                      |
| 第 3 章 控制平面四环节  | `src/text_adventure_rpg/engine.py`                              |
| 第 4 章 项目级上下文    | `CLAUDE.md`                                                     |
| 第 5 章 权限/沙箱/Hooks | `.claude/settings.json`                                         |
| 第 6 章 Agent Loop      | `src/text_adventure_rpg/__main__.py`                            |
| 第 7 章 任务分解        | `src/text_adventure_rpg/engine.py` 中的任务循环                 |
| 第 8 章 多文件协作      | `src/text_adventure_rpg/scenes.py` + `items.py` + `npcs.py` |
| 第 9 章 错误恢复        | `src/text_adventure_rpg/engine.py` 的回滚/重试/降级             |
| 第 10 章 持久化         | `src/text_adventure_rpg/persistence.py`                         |

### 书二《Claude Code 从入门到项目实践》（卷三·文字冒险 RPG 游戏）

| 章节                         | 对应代码                                                                                       |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| 第 27 章 项目立项与架构设计  | `src/text_adventure_rpg/__main__.py`（项目骨架、入口分配）                                   |
| 第 28 章 场景图与状态机引擎  | `src/text_adventure_rpg/scenes.py`（房间/地图/状态机/导航）                                  |
| 第 29 章 NPC、物品与对话系统 | `src/text_adventure_rpg/npcs.py` + `items.py`（NPC 行为建模/多分支对话/物品背包）          |
| 第 30 章 战斗系统与数值平衡  | `src/text_adventure_rpg/combat.py` + `character.py` + `formulas.py`                      |
| 第 31 章 动态叙事与 LLM 集成 | `src/text_adventure_rpg/narrative.py`（`client=None` 走本地确定性模板，CI 不依赖 LLM Key） |
| 第 32 章 存档、UI 与测试     | `src/text_adventure_rpg/persistence.py` + `validators.py`（原子存档/双形态 UI/自动化测试） |
| 第 33 章 调试、迭代与发布    | 整体调试流程与发布脚本                                                                         |

## 快速开始

```bash
# 安装（需要 Python 3.10+）
pip install -e .

# 运行
text-rpg          # 书一核心探索版（__main__.py，perceive→plan→act→verify 主循环）
text-full-rpg     # 书二战斗集成版（game.py，character + combat + formulas + narrative）

# 也可用模块方式运行核心探索版
python -m text_adventure_rpg

# 跑测试
pytest
```

## 部署架构

单进程命令行游戏，无外部依赖。状态以 JSON 文件持久化到 `~/.text-adventure-rpg/saves/`。

```text
玩家输入 ──▶ Engine（控制平面）
                │
                ├─ 感知 perceive ──▶ Scene 加载
                ├─ 计划 plan     ──▶ NPC 行为
                ├─ 执行 act      ──▶ Item / 战斗应用
                └─ 验证 verify   ──▶ State 持久化
```

## 配套书籍

本仓库是以下书籍的可部署配套案例（**目前两本，后续可能新增**）：

- **《Harness 工程：围绕 Claude Code 构建可靠系统》**（卷一·卷二，核心篇）— 南荣相如

  - 对应核心探索版：`__main__` / `engine` / `scenes` / `items` / `npcs` / `persistence` / `validators`
  - 代码片段索引：[claudecode-harness-book](https://github.com/zcqiand/claudecode-harness-book)
- **《Claude Code 从入门到项目实践》**（卷三·文字冒险 RPG 游戏）— 南荣相如

  - 对应战斗集成版：`character` / `combat` / `formulas` / `narrative` / `game`
  - 代码片段索引：[claude-code-book](https://github.com/zcqiand/claude-code-book)
  - 电子书籍网址：[亚马逊](https://www.amazon.com/dp/B0H3M3B8GG)

**Issues**：[https://github.com/zcqiand/text-adventure-rpg/issues](https://github.com/zcqiand/text-adventure-rpg/issues)
