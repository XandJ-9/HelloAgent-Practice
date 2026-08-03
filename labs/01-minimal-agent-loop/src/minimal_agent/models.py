"""Shared data structures for the Agent Loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Action:
    """A structured action chosen by the brain."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """The Thought and Action produced in one decision step."""

    thought: str
    action: Action


@dataclass(frozen=True)
class Step:
    """A complete Thought-Action-Observation record."""

    number: int
    decision: Decision
    observation: str


StopReason = Literal["finished", "max_steps"]
