"""Web 层配置：fail-fast 加载环境变量。

家族范式（ai-tutoring-multi-agent 同款）：`LLM_MODE` 必填且只认 ``mock|live``，
禁止 env 默认值兜底——缺配置就在启动时炸，而不是在玩家冒险途中炸。
live 模式还需 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` 三键齐全
（OpenAI 兼容端点直调，家族三兄弟同款接线）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    """Web 服务运行配置。"""

    llm_mode: str                 # mock | live
    llm_base_url: str             # OpenAI 兼容根路径，如 https://api.minimaxi.com/v1
    llm_api_key: str              # live 模式必填；mock 恒空
    llm_model: str                # live 模式必填，如 MiniMax-M2.5
    app_port: int                 # dev 家族端口 8805
    saves_dir: Path | None        # battle- 存档目录；None = ~/.text-adventure-rpg/saves


def load_settings(
    environ: Mapping[str, str] | None = None,
    env_file: Path | str | None = None,
) -> Settings:
    """从进程环境 + .env 文件合并加载配置。

    合并优先级：进程环境 > .env 文件。任何缺失/非法键立即抛 ``RuntimeError``，
    错误信息直接指出缺什么、怎么补。
    """

    merged: dict[str, str] = {}
    if env_file is not None:
        merged.update(_read_env_file(Path(env_file)))
    # environ=None 表示读真实进程环境（服务入口）；显式传 dict 则以注入为准（测试）。
    merged.update(os.environ if environ is None else environ)

    mode = merged.get("LLM_MODE", "").strip()
    if not mode:
        raise RuntimeError(
            "缺少 LLM_MODE 环境变量。请设为 mock（离线确定性叙事）或 live（LLM 渲染叙事）。"
            "参考 .env.example。"
        )
    if mode not in {"mock", "live"}:
        raise RuntimeError(f"LLM_MODE 只认 mock|live，实际为: {mode!r}")

    base_url = merged.get("LLM_BASE_URL", "").strip()
    api_key = merged.get("LLM_API_KEY", "").strip()
    model = merged.get("LLM_MODEL", "").strip()
    if mode == "live":
        missing = [
            name
            for name, value in (
                ("LLM_BASE_URL", base_url),
                ("LLM_API_KEY", api_key),
                ("LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"LLM_MODE=live 需要补齐环境变量: {', '.join(missing)}（OpenAI 兼容端点）。"
            )

    port_raw = merged.get("APP_PORT", "8805")
    try:
        app_port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"APP_PORT 必须是整数，实际为: {port_raw!r}") from exc

    saves_raw = merged.get("APP_SAVES_DIR", "").strip()
    saves_dir = Path(saves_raw) if saves_raw else None

    return Settings(
        llm_mode=mode,
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_model=model,
        app_port=app_port,
        saves_dir=saves_dir,
    )


def _read_env_file(path: Path) -> dict[str, str]:
    """解析 .env 文件：KEY=VALUE 行，# 注释与空行跳过，值两侧引号剥掉。"""

    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if "=" not in cleaned:
            continue
        key, _, value = cleaned.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result
