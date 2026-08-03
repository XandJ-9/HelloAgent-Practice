---
title: 最小 Agent Loop 实验
status: completed
tags:
  - lab
  - agent-loop
  - python
  - uv
---

# 最小 Agent Loop 实验

返回：[[labs/README|实验索引]]

## 学习目标

用 Python 实现最小的“观察 → 决策 → 行动 → 获取反馈”循环，理解 Agent 与单次 LLM 调用的本质差异。

## 为什么这样设计

飞书原文第 1.2～1.3 节强调三个核心点：

1. 智能体不是一次性完成任务，而是在感知、思考、行动和观察之间循环。
2. `Thought` 和 `Action` 应采用明确的结构，工具结果作为 `Observation` 进入下一轮。
3. 收集到足够信息时调用 `finish`，同时设置最大循环次数作为安全停止条件。

本实验因此暂时不接入真实 LLM，而是使用可预测的 `RuleBasedBrain`。它保留完整循环和可替换的 Brain 接口，让注意力集中在 Agent 的工程结构上。后续接入 LLM 时，只需新增一个实现 `decide()` 的 Brain，无需改动主循环。

## 项目结构

```text
01-minimal-agent-loop/
├── data/
│   └── example.txt
├── src/minimal_agent/
│   ├── agent.py       # Agent Loop 和停止条件
│   ├── brain.py       # 决策接口与规则大脑
│   ├── cli.py         # 命令行入口
│   ├── models.py      # Action、Decision、Step
│   └── tools.py       # 计算器和受限文件读取工具
├── tests/
│   └── test_agent.py
├── .python-version
├── pyproject.toml
└── uv.lock
```

## 环境准备

本知识库中的 Python 项目统一使用 [uv](https://docs.astral.sh/uv/) 管理 Python、依赖和运行命令。

在本实验目录执行：

```bash
uv sync
```

`uv` 会根据 `.python-version`、`pyproject.toml` 和 `uv.lock` 创建独立环境。

## 运行实验

默认运行计算任务：

```bash
uv run minimal-agent
```

指定一个计算任务：

```bash
uv run minimal-agent "计算 (23 + 7) * 4"
```

读取实验数据目录中的文件：

```bash
uv run minimal-agent "读取 example.txt"
```

你会看到两轮输出：第一轮选择并执行工具，第二轮读取 Observation 后调用 `finish`。

## 运行测试

```bash
uv run python -m unittest discover -s tests -v
```

测试覆盖：

- 正常调用计算器并结束。
- 读取允许目录中的文本。
- 工具失败转化为 Observation。
- 未注册工具不会导致循环崩溃。
- 重复行动会被最大循环次数终止。

## 验收标准

- [x] 能清楚看到每轮 Observe、Think、Act 和 Result。
- [x] 可以正确调用计算器和文本读取工具。
- [x] 工具错误不会导致程序直接崩溃，而是成为 Observation。
- [x] 有最大循环次数，避免无限运行。
- [x] 包含 5 个自动化测试案例。
- [ ] 完成后在 `reviews/experiments/` 写一份复盘。

## 建议阅读顺序

1. 先运行一次命令，观察两轮日志。
2. 阅读 `models.py`，理解结构化消息。
3. 阅读 `agent.py` 中的 `run()`，画出循环。
4. 阅读 `tools.py`，观察工具约束和错误转换。
5. 阅读测试中的异常与最大轮数案例。
6. 尝试新增一个 `word_count` 工具。

## 关联知识

- [[notes/01-agent-workflow-llm-app#3. Agent 是什么|Agent 是什么]]
- [[GLOSSARY#核心术语表|核心术语表]]
