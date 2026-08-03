"""Command-line entry point for the experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

from .agent import Agent
from .brain import RuleBasedBrain
from .tools import default_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行最小 Agent Loop")
    parser.add_argument(
        "task",
        nargs="?",
        default="计算 23 * 4",
        help='任务，例如："计算 23 * 4" 或 "读取 example.txt"',
    )
    parser.add_argument("--max-steps", type=int, default=5)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[2]
    agent = Agent(
        RuleBasedBrain(),
        default_tools(project_root / "data"),
        max_steps=args.max_steps,
    )
    agent.run(args.task)


if __name__ == "__main__":
    main()
