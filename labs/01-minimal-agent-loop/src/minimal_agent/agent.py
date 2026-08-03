"""The minimal Observe-Think-Act-Observe loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .brain import Brain
from .models import Step, StopReason
from .tools import Tool, ToolError


@dataclass(frozen=True)
class AgentResult:
    answer: str
    stop_reason: StopReason
    steps: tuple[Step, ...]


class Agent:
    def __init__(
        self,
        brain: Brain,
        tools: dict[str, Tool],
        *,
        max_steps: int = 5,
        verbose: bool = True,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps 必须至少为 1")
        self.brain = brain
        self.tools = tools
        self.max_steps = max_steps
        self.verbose = verbose

    def run(self, task: str) -> AgentResult:
        """Run until the brain calls finish or the safety limit is reached."""

        history: list[Step] = []
        self._print(f"Task: {task}")

        for step_number in range(1, self.max_steps + 1):
            self._print(f"\n--- Loop {step_number} ---")
            self._print(f"Observe: {self._current_observation(task, history)}")

            decision = self.brain.decide(task, tuple(history))
            self._print(f"Thought: {decision.thought}")
            self._print(
                f"Action: {decision.action.name}({decision.action.arguments})"
            )

            if decision.action.name == "finish":
                answer = str(decision.action.arguments.get("answer", ""))
                self._print(f"Result: {answer}")
                return AgentResult(answer, "finished", tuple(history))

            observation = self._execute(
                decision.action.name, decision.action.arguments
            )
            self._print(f"Observation: {observation}")
            history.append(Step(step_number, decision, observation))

        answer = f"达到最大循环次数 {self.max_steps}，任务未完成。"
        self._print(f"Result: {answer}")
        return AgentResult(answer, "max_steps", tuple(history))

    def _execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.tools.get(tool_name)
        if tool is None:
            return f"工具错误：未注册工具 {tool_name!r}"
        try:
            return tool(**arguments)
        except ToolError as exc:
            return f"工具错误：{exc}"
        except TypeError as exc:
            return f"参数错误：{exc}"
        except Exception as exc:  # A tool failure becomes an observation.
            return f"工具发生未预期错误：{type(exc).__name__}: {exc}"

    @staticmethod
    def _current_observation(task: str, history: list[Step]) -> str:
        if not history:
            return f"用户任务：{task}"
        return history[-1].observation

    def _print(self, message: str) -> None:
        if self.verbose:
            print(message)
