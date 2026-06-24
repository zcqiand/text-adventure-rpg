"""LLM 动态叙事集成（可降级，CI 不依赖真实 LLM Key）。

卷三第 31 章「LLM 动态叙事」配套实物。设计要点：

- **依赖注入**：``Narrator`` 不绑定任何具体 LLM SDK，通过 :class:`NarrationClient`
  Protocol 接受外部 client；测试与生产各自注入实现。
- **本地降级**：``client=None`` 时走纯字符串模板，**零随机、零网络**，保证
  相同 scene+context → 相同输出，使测试确定（CI 无需 LLM Key）。
- 这是书中「在不确定的外部依赖前加一层自己的抽象」的直接演示。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NarrationClient(Protocol):
    """叙事后端的抽象协议。

    任何具备 ``generate(prompt) -> str`` 的对象都满足此协议，
    不必显式继承（structural typing）。
    """

    def generate(self, prompt: str) -> str:
        """根据 prompt 生成叙事文本。"""
        ...


class Narrator:
    """叙事生成器：有 LLM client 时调用之，否则本地降级。

    Args:
        client: 实现 :class:`NarrationClient` 的对象；``None`` 时启用本地降级。
    """

    def __init__(self, client: NarrationClient | None = None) -> None:
        self.client = client

    def narrate(self, scene: str, context: dict) -> str:
        """为给定场景与上下文产出叙事文本。

        Args:
            scene: 场景标识，如 ``"tavern"``、``"dungeon"``。
            context: 上下文键值（角色名、时间、情绪等），值会被 ``str()`` 化。

        Returns:
            叙事文本。``client=None`` 时确定性非空。
        """
        if self.client is not None:
            prompt = self._build_prompt(scene, context)
            return self.client.generate(prompt)
        return self._fallback(scene, context)

    @staticmethod
    def _build_prompt(scene: str, context: dict) -> str:
        """把 scene + context 拼成给 LLM 的 prompt。"""
        ctx_str = ", ".join(f"{k}={v}" for k, v in context.items()) or "(empty)"
        return f"[narrate] scene={scene}; context: {ctx_str}"

    @staticmethod
    def _fallback(scene: str, context: dict) -> str:
        """本地降级：纯字符串拼接，确定性、非随机。

        相同 (scene, context) → 相同输出。把 context 的值织入文本，
        便于测试断言「上下文确实进入了叙事」。
        """
        parts = [f"scene:{scene}"]
        for key, value in context.items():
            parts.append(f"{key}:{value}")
        return "[" + "|".join(parts) + "]"
