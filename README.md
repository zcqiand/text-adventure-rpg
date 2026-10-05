# 文字冒险 RPG 游戏

单进程、零外部依赖的命令行文字冒险 RPG + 可选 Web/API 层，配套《Harness 工程：围绕 Claude Code 构建可靠系统》卷一·卷二。

## 快速开始

```bash
pip install -e .          # 安装依赖（Python 3.10+）
text-rpg                  # 核心探索版（书一案例）
text-full-rpg             # 战斗集成版（历史入口，原书二卷三案例；该书已换绑弃用此仓，入口保留）
LLM_MODE=mock text-rpg-web  # Web/API 层（FastAPI，默认 127.0.0.1:8805）
pytest -q                 # 全量测试
```

## Web 前端

`frontend/` 是 React 18 + Vite + TS 单页（战斗版 Web 化：选职业 → 探索 → 战斗 → 存读档，磷光 CRT 终端风）：

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run build             # tsc strict + vite 构建门
npm run dev               # vite dev 5805，/api 代理到 8805
```

前端代码只写同源相对 `/api`，dev 由 vite 代理承接；后端 `.env` 配置见 `.env.example`（`LLM_MODE=live` 时接 OpenAI 兼容叙事端点，密钥只放本地 `.env`，绝不入库）。

## 功能特性

- **双入口并行**：`text-rpg` 核心探索版 / `text-full-rpg` 战斗集成版，共享场景数据
- **Web/API 层**：FastAPI 包战斗版状态机（`text-rpg-web`），React 前端三态游玩；CLI 入口保持零第三方依赖，API 依赖仅 fastapi+uvicorn
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

配套版本：`v2.0.0-20260625`（本书第 1—10 章引用源文件以此 tag 为准；`v2.0.1-20261005` 恢复第 5 章实物 `.claude/settings.json` 并补充测试，引用文件内容不变）

| 章 | 主题 | 对应源文件 |
| :--- | :--- | :--- |
| 1 Harness 的由来 | 案例导引 | 仓库整体结构 |
| 4 上下文治理 | 项目级上下文 | `CLAUDE.md` |
| 5 权限与沙箱 | 权限/沙箱/Hooks 实物示例 | `.claude/settings.json` |
| 6 思考行动检查 | Agent Loop 主循环 | `src/text_adventure_rpg/__main__.py` |
| 7 复杂问题分解 | 任务分解 | `src/text_adventure_rpg/engine.py` |
| 8 多文件修改 | 多文件协作 | `src/text_adventure_rpg/{scenes,items,npcs}.py` |
| 9 AI 错误修正 | 错误恢复 | `src/text_adventure_rpg/engine.py` |
| 10 跨会话恢复 | 持久化 | `src/text_adventure_rpg/persistence.py` |

## 快速链接

- [CLAUDE.md](CLAUDE.md) — 开发约定与编码规范
- [功能规格.md](docs/功能规格.md) — 功能名称、描述与验收标准
