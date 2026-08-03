"""Decision-making interface and a deterministic starter implementation."""

from __future__ import annotations

from typing import Protocol, Sequence

from .models import Action, Decision, Step


class Brain(Protocol):
    """Anything that can choose the next action can drive the Agent Loop."""

    def decide(self, task: str, history: Sequence[Step]) -> Decision: ...


class RuleBasedBrain:
    """A predictable brain for learning the loop before connecting an LLM.

    Supported task forms:
    - ``计算 23 * 4``
    - ``读取 example.txt``
    """

    def decide(self, task: str, history: Sequence[Step]) -> Decision:
        if history:
            last_observation = history[-1].observation
            return Decision(
                thought="我已经获得工具反馈，可以基于观察结束任务。",
                action=Action("finish", {"answer": last_observation}),
            )

        normalized = task.strip()
        if normalized.startswith("计算"):
            expression = normalized.removeprefix("计算").strip()
            return Decision(
                thought="任务需要精确计算，我应选择计算器工具。",
                action=Action("calculator", {"expression": expression}),
            )
        if normalized.startswith("读取"):
            path = normalized.removeprefix("读取").strip()
            return Decision(
                thought="任务需要获取文件内容，我应选择文本读取工具。",
                action=Action("read_text", {"path": path}),
            )
        return Decision(
            thought="当前规则大脑不理解这个任务，需要明确告知支持的格式。",
            action=Action(
                "finish",
                {"answer": "无法处理该任务。请使用“计算 表达式”或“读取 文件名”。"},
            ),
        )
