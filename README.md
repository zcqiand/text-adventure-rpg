# 文字冒险 RPG 游戏

单进程、零外部依赖的命令行文字冒险 RPG，配套《Harness 工程》和《Claude Code 从入门到项目实践》。

## 快速开始

```bash
pip install -e .          # 安装依赖（Python 3.10+）
text-rpg                  # 书一核心探索版
text-full-rpg             # 书二战斗集成版
pytest -q                 # 全量测试
```

## 功能特性

- **双入口并行**：`text-rpg` 核心探索版 / `text-full-rpg` 战斗集成版，共享场景数据
- **场景探索**：`go <方向>` / `look`，敌人在场时无法离开
- **回合制战斗**：普通攻击 + 技能（耗 MP、伤害更高；MP 不足自动降级）
- **三职业**：战士（高 HP）/ 法师（高 MP）/ 盗贼（高攻）
- **多槽位存档**：手动 `save`/`load` + 每 5 回合自动 checkpoint（环形保留最近 3 份）
- **撤销**：`undo` 玩家级回退最近 10 步
- **动态叙事**：可选 LLM 渲染，默认本地确定性模板（零网络依赖）

## 技术栈

| 技术 | 版本 |
| :--- | :--- |
| Python | 3.10+ |
| 标准库优先 | — |
| 测试框架 | pytest |

> 依赖版本与 `version-lock.json` 的 `version_lock` 一致，不引入 lock 外的库。

## 配套书籍及章节映射

### 书一《Harness 工程：围绕 Claude Code 构建可靠系统》（卷一·卷二）

| 章 | 主题 | 对应源文件 |
| :--- | :--- | :--- |
| 1 | 案例介绍 | 仓库整体结构 |
| 3 | 控制平面四环节 | `src/text_adventure_rpg/engine.py` |
| 4 | 项目级上下文 | `CLAUDE.md` |
| 5 | 权限/沙箱/Hooks | `.claude/settings.json` |
| 6 | Agent Loop | `src/text_adventure_rpg/__main__.py` |
| 7 | 任务分解 | `src/text_adventure_rpg/engine.py` |
| 8 | 多文件协作 | `src/text_adventure_rpg/{scenes,items,npcs}.py` |
| 9 | 错误恢复 | `src/text_adventure_rpg/engine.py` |
| 10 | 持久化 | `src/text_adventure_rpg/persistence.py` |

### 书二《Claude Code 从入门到项目实践》（卷三）

| 章 | 主题 | 对应源文件 |
| :--- | :--- | :--- |
| 27 | 项目立项与架构设计 | `src/text_adventure_rpg/__main__.py` |
| 28 | 场景图与状态机引擎 | `src/text_adventure_rpg/scenes.py` |
| 29 | NPC、物品与对话系统 | `src/text_adventure_rpg/{npcs,items}.py` |
| 30 | 战斗系统与数值平衡 | `src/text_adventure_rpg/{combat,character,formulas}.py` |
| 31 | 动态叙事与 LLM 集成 | `src/text_adventure_rpg/narrative.py` |
| 32 | 存档、UI 与测试 | `src/text_adventure_rpg/{persistence,validators}.py` |
| 33 | 调试、迭代与发布 | 整体调试流程与发布脚本 |

## 快速链接

- [功能规格文档.md](功能规格文档.md) — 功能名称、描述与验收标准
- [CLAUDE.md](CLAUDE.md) — 开发约定与编码规范
