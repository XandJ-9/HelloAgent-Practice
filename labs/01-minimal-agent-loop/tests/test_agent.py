from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from minimal_agent.agent import Agent
from minimal_agent.brain import RuleBasedBrain
from minimal_agent.models import Action, Decision
from minimal_agent.tools import calculator, default_tools


class RepeatingBrain:
    def decide(self, task, history):
        return Decision("继续执行同一个动作。", Action("calculator", {"expression": "1+1"}))


class UnknownToolBrain:
    def decide(self, task, history):
        if history:
            return Decision("观察到错误后结束。", Action("finish", {"answer": history[-1].observation}))
        return Decision("尝试一个不存在的工具。", Action("missing_tool"))


class AgentLoopTests(unittest.TestCase):
    def test_calculation_uses_tool_then_finishes(self):
        with TemporaryDirectory() as directory:
            agent = Agent(
                RuleBasedBrain(), default_tools(Path(directory)), verbose=False
            )
            result = agent.run("计算 23 * 4")

        self.assertEqual(result.answer, "92")
        self.assertEqual(result.stop_reason, "finished")
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.steps[0].decision.action.name, "calculator")

    def test_reads_text_from_allowed_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lesson.txt").write_text("Agent Loop", encoding="utf-8")
            agent = Agent(RuleBasedBrain(), default_tools(root), verbose=False)

            result = agent.run("读取 lesson.txt")

        self.assertEqual(result.answer, "Agent Loop")

    def test_tool_error_becomes_observation(self):
        agent = Agent(RuleBasedBrain(), {"calculator": calculator}, verbose=False)

        result = agent.run("计算 1 / 0")

        self.assertEqual(result.stop_reason, "finished")
        self.assertIn("工具错误", result.answer)
        self.assertIn("无法计算表达式", result.steps[0].observation)

    def test_unknown_tool_does_not_crash_loop(self):
        agent = Agent(UnknownToolBrain(), {}, verbose=False)

        result = agent.run("任意任务")

        self.assertIn("未注册工具", result.answer)
        self.assertEqual(len(result.steps), 1)

    def test_max_steps_stops_infinite_loop(self):
        agent = Agent(
            RepeatingBrain(), {"calculator": calculator}, max_steps=3, verbose=False
        )

        result = agent.run("永远不要结束")

        self.assertEqual(result.stop_reason, "max_steps")
        self.assertEqual(len(result.steps), 3)


if __name__ == "__main__":
    unittest.main()
