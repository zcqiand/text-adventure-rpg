# text-adventure-rpg — 仓库工作约定（供 Claude Code）

本仓为可运行配套工程，是书稿代码块的 **source of truth**。

## 项目定位

单进程、零外部依赖的命令行文字冒险 RPG，用于演示控制平面、多文件协作、上下文治理、错误恢复、持久化等能力。

## 铁律

- **TDD**：每个模块先写失败测试 → 跑确认失败 → 实现 → 跑确认绿 → commit。
- **版本钉死**：依赖与 `version-lock.json` 的 `version_lock` 一致；不引入 lock 外的库。
- **只增不改**：扩充时不动现有模块签名/行为；新模块独立测试，CI 双跑。
- **mock-friendly**：`pip install -e . && pytest -q` 必须在无 Key、无 Docker、无网下全绿。

## 技术栈（版本钉死于 `version-lock.json`）

Python 3.10+ / 标准库优先 / pytest

## 验收

```bash
pip install -e .    # 离线可用
pytest -q           # 必须全绿，无需 Key/Docker/网络
```

Web/API 层（战斗版）：

```bash
LLM_MODE=mock text-rpg-web        # 服务起 8805，/api/health 返回 {"ok":true,"mode":"mock"}
cd frontend && npm run build      # 前端 tsc strict + vite 构建门（npm 走 npmmirror）
```

## 编码约定

- **数据驱动**：场景/物品/NPC 必须从 `data/` 加载，禁止硬编码到 Python 文件。
- **存档原子性**：写入存档时先写临时文件再 `os.replace`，禁止直接覆盖。
- **错误处理**：所有文件 I/O 必须捕获 `FileNotFoundError` 和 `json.JSONDecodeError`，并给出可读错误信息。
- **零伪代码**：禁止 `pass` 占位、`TODO` 占位、`...` 占位，每段代码必须可运行。

## 细则（docs/conventions/，按需引用）

- 目录结构与模块职责 → `docs/conventions/structure.md`
- Tag 规约：Release 格式 `v<MAJOR>.<MINOR>.<PATCH>-<YYYYMMDD>`，禁止删/覆盖，
  禁止 `git push --tags`（显式 `push origin <tag>`）→ `docs/conventions/tagging.md`
