# text-adventure-rpg — 仓库工作约定（供 Claude Code）

本仓为《Harness 工程》与《Claude Code 从入门到项目实践》案例仓（文字冒险 RPG）的可运行配套工程，是书稿代码块的 **source of truth**。

## 项目定位

单进程、零外部依赖的命令行文字冒险 RPG，用于演示控制平面、多文件协作、上下文治理、错误恢复、持久化等能力。

## 铁律

- **TDD**：每个模块先写失败测试 → 跑确认失败 → 实现 → 跑确认绿 → commit。
- **版本钉死**：依赖与 `version-lock.json` 的 `version_lock` 一致；不引入 lock 外的库。
- **tag 即放行**：全量回归绿后打 `v<MAJOR>.<MINOR>-<NNN>`（NNN=项目号）。
- **只增不改**：扩充时不动现有模块签名/行为；新模块独立测试，CI 双跑。
- **mock-friendly**：`pip install -e . && pytest -q` 必须在无 Key、无 Docker、无网下全绿。

## 技术栈与版本（钉死于 version-lock.json）

- Python 3.10+
- 标准库优先
- pytest

## 验收

```bash
pip install -e .    # 离线可用（首次需联网，之后 node_modules 已就绪）
pytest -q           # 必须全绿，无需 Key/Docker/网络
```

## 目录结构

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

## 编码约定

- **数据驱动**：场景/物品/NPC 必须从 `data/` 加载，禁止硬编码到 Python 文件。
- **存档原子性**：写入存档时先写临时文件再 `os.replace`，禁止直接覆盖。
- **错误处理**：所有文件 I/O 必须捕获 `FileNotFoundError` 和 `json.JSONDecodeError`，并给出可读错误信息。
- **零伪代码**：禁止 `pass` 占位、`TODO` 占位、`...` 占位，每段代码必须可运行。
