"""OpenAI 兼容叙事客户端：stdlib urllib 直调，零第三方依赖。

实现 :class:`text_adventure_rpg.narrative.NarrationClient` Protocol
（``generate(prompt) -> str``），把「LLM 渲染叙事」接到家族统一的
OpenAI 兼容端点直调先例上。仓库铁律是零第三方运行时依赖，所以
不用 openai SDK，标准库 ``urllib.request`` 足够——这也是第 31 章
「在不确定的外部依赖前加一层自己的抽象」的又一实物。

坑位（家族指纹沉淀）：MiniMax 系模型会内联输出 ``<think>…</think>``
思维链，玩家不该看到——这里统一剥离。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class NarrationError(RuntimeError):
    """叙事后端调用失败（网络/鉴权/响应形状不符）。"""


def strip_think(text: str) -> str:
    """剥掉内联思维链标签并去首尾空白。"""
    return _THINK_RE.sub("", text).strip()


class OpenAICompatNarrator:
    """OpenAI 兼容 ``/chat/completions`` 叙事后端。

    Args:
        base_url: 兼容端点根路径，如 ``https://api.minimaxi.com/v1``。
        api_key: Bearer 凭据。
        model: 模型名，如 ``MiniMax-M2.5``。
        timeout: 单次请求超时秒数。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """按 NarrationClient 协议生成一段叙事文本。

        Raises:
            NarrationError: 请求失败或响应缺少 ``choices[0].message.content``。
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise NarrationError(f"叙事后端调用失败: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise NarrationError(f"叙事后端响应形状不符: {body!r}") from exc
        if not isinstance(content, str):
            raise NarrationError(f"叙事后端返回的 content 不是字符串: {content!r}")
        return strip_think(content)
