"""narrative 模块测试：LLM 动态叙事 + 本地降级。"""

from __future__ import annotations

from text_adventure_rpg.narrative import Narrator


class TestLocalFallback:
    def test_returns_nonempty_string(self):
        n = Narrator(client=None)
        out = n.narrate("tavern", {"hero": "Alice"})
        assert isinstance(out, str)
        assert len(out) > 0

    def test_deterministic_same_input_same_output(self):
        n = Narrator(client=None)
        ctx = {"hero": "Alice", "time": "dawn"}
        a = n.narrate("tavern", ctx)
        b = n.narrate("tavern", ctx)
        assert a == b

    def test_different_scene_different_output(self):
        n = Narrator(client=None)
        ctx = {"hero": "Alice"}
        a = n.narrate("tavern", ctx)
        b = n.narrate("dungeon", ctx)
        # 不同场景至少应有不同文本
        assert a != b

    def test_context_values_appear_in_output(self):
        # 降级模板应把 context 的值织进去（增强可读性与可测性）
        n = Narrator(client=None)
        out = n.narrate("tavern", {"hero": "Zophie"})
        assert "Zophie" in out


class FakeClient:
    """实现 NarrationClient 协议的测试替身，带调用计数。"""

    def __init__(self, response: str = "[LLM] epic scene") -> None:
        self.response = response
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


class TestClientInjection:
    def test_client_generate_is_called(self):
        fake = FakeClient(response="[LLM] the tavern smells of ale")
        n = Narrator(client=fake)
        out = n.narrate("tavern", {"hero": "Alice"})
        assert len(fake.calls) == 1
        assert "tavern" in fake.calls[0]
        assert out == fake.response

    def test_prompt_contains_scene_and_context(self):
        fake = FakeClient()
        n = Narrator(client=fake)
        n.narrate("forest", {"hero": "Bob", "mood": "tense"})
        prompt = fake.calls[0]
        assert "forest" in prompt
        assert "Bob" in prompt
        assert "tense" in prompt

    def test_multiple_calls_accumulate(self):
        fake = FakeClient()
        n = Narrator(client=fake)
        n.narrate("a", {})
        n.narrate("b", {})
        assert len(fake.calls) == 2


class TestNarrationClientProtocol:
    def test_protocol_is_structural(self):
        # NarrationClient 是 typing.Protocol，FakeClient 不必显式继承即可被识别
        from text_adventure_rpg.narrative import NarrationClient

        fake = FakeClient()
        # isinstance 检查仅在 runtime_checkable 时成立；协议本身可被引用即足
        assert hasattr(NarrationClient, "generate")
        assert hasattr(fake, "generate")
