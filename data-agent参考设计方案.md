## 数据agent设计开发
开发一个web版本的对话聊天式的数据agent，通过自然语言对话的方式，让agent做对应的数据分析处理工作，按照下面的设计蓝图开发，其中数据库可以暂时使用sqlite。要求具备一个基本的对话聊天框，能够展示agent的分析过程。
---

### 一、 系统架构与交互设计

在 FastAPI 中集成 Agent，核心原则是**将 Web 路由（Router）与 Agent 状态机（Graph）解耦**。

1. **前端交互**：用户在界面输入自然语言。由于 Agent 执行查表、写SQL、跑数据的过程可能耗时 5~30 秒，强烈建议后端采用 **SSE (Server-Sent Events) 流式返回**，前端实时显示：“🔍 正在寻找相关数据表...” -> “✍️ 正在生成 SQL...” -> “✅ 执行成功，正在渲染数据...”。
2. **后端 FastAPI 层**：接收请求，鉴权，然后触发内部的 Agent 工作流。
3. **Agent 工作流层**：基于 **LangGraph** 构建。包含实体抽取、检索知识库、编写 SQL、执行与纠错等节点。
4. **数据操作层**：使用 `SQLAlchemy` 连接业务**只读数据库**执行查询。

---

### 二、 推荐的工程目录结构

在现有的 FastAPI 项目中，建议新增一个单独的 `agent` 模块：

```text
├── app/
│   ├── main.py
│   ├── api/
│   │   └── endpoints/
│   │       └── chat.py          <-- FastAPI 接口路由
│   ├── core/
│   │   ├── config.py            <-- 配置 (DB账号, LLM API Key)
│   │   └── security.py          <-- 鉴权拦截
│   ├── database/
│   │   └── session.py           <-- 业务数据库连接 (Read-Only)
│   └── agent/                   <-- 🌟 新增：Agent 核心目录
│       ├── state.py             <-- 定义 Agent 的全局状态 (State)
│       ├── nodes/
│       │   ├── retriever.py     <-- 找表和找字典节点
│       │   ├── sql_coder.py     <-- 写 SQL 节点
│       │   └── executor.py      <-- 执行 SQL 节点
│       ├── workflow.py          <-- LangGraph 编排（连接所有Node）
│       └── prompts.py           <-- 大模型提示词模板
```

---

### 三、 核心代码落地指北（Python + LangGraph + FastAPI）

#### 1. 定义 Agent 的状态记录器 (agent/state.py)
在 Agent 工作过程中，需要一个全局的“记事本”在各个节点间传递数据。
```python
from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    query: str                  # 运营人员的原始问题
    selected_tables: List[str]  # RAG 找到的相关表结构（DDL/注释）
    generated_sql: str          # 大模型生成的 SQL
    execution_result: List[Dict[str, Any]] # SQL 执行返回的数据
    error_msg: Optional[str]    # 如果执行报错，记录错误信息
    retry_count: int            # 记录重试次数，防止死循环
```

#### 2. 构建 Agent 节点 (agent/nodes/...)
把每一步动作写成一个单独的函数。以核心的“生成 SQL”和“执行 SQL”为例：

```python
# agent/nodes/sql_coder.py
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agent.state import AgentState

llm = ChatOpenAI(model="gpt-4o", temperature=0) # 建议使用推理能力强的模型

def generate_sql_node(state: AgentState) -> dict:
    prompt = ChatPromptTemplate.from_template(
        """你是一个资深数据分析师。根据用户的需求和以下表结构，编写可执行的 SQL。
        用户需求: {query}
        可用表结构: {selected_tables}
        历史错误信息(如果有，请修复它): {error_msg}

        注意：必须返回纯净的 SQL 语句，禁止任何 Markdown 标记。"""
    )
    chain = prompt | llm
    sql_result = chain.invoke({
        "query": state["query"],
        "selected_tables": "\n".join(state["selected_tables"]),
        "error_msg": state.get("error_msg", "")
    })

    return {"generated_sql": sql_result.content}

# agent/nodes/executor.py
from sqlalchemy import text
from app.database.session import read_only_engine # 引入只读库引擎

def execute_sql_node(state: AgentState) -> dict:
    sql = state["generated_sql"]
    try:
        # 这里必须做基础的安全校验（如拦截 DELETE/DROP，限制 LIMIT）
        if "delete" in sql.lower() or "drop" in sql.lower():
            raise ValueError("禁止执行破坏性查询。")

        with read_only_engine.connect() as conn:
            result = conn.execute(text(sql))
            data = [dict(row) for row in result.fetchall()]
        return {"execution_result": data, "error_msg": None} # 执行成功，清空错误
    except Exception as e:
        # 捕获报错，准备让大模型重写
        return {"error_msg": str(e), "retry_count": state.get("retry_count", 0) + 1}
```

#### 3. 编排工作流流转引擎 (agent/workflow.py)
利用 LangGraph 将节点组合起来，并设置**“出错重试”的路由规则**。

```python
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes.retriever import retrieve_schema_node
from app.agent.nodes.sql_coder import generate_sql_node
from app.agent.nodes.executor import execute_sql_node

def route_after_execution(state: AgentState):
    # 如果有错误，且重试次数小于 3，打回重新写 SQL
    if state.get("error_msg") and state.get("retry_count", 0) < 3:
        return "generate_sql"
    # 如果成功，或者重试达上限，结束流程
    return END

# 初始化图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("retrieve_schema", retrieve_schema_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)

# 设置流转规则
workflow.set_entry_point("retrieve_schema")
workflow.add_edge("retrieve_schema", "generate_sql")
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_conditional_edges("execute_sql", route_after_execution)

# 编译成可运行的 Agent
data_agent = workflow.compile()
```

#### 4. FastAPI 接口实现 (app/api/endpoints/chat.py)
在 FastAPI 中暴露接口。为了给运营提供极佳的交互体验，强烈建议使用 `StreamingResponse`，将 Agent 跑到了哪一步实时推给前端。

```python
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.agent.workflow import data_agent

router = APIRouter()

@router.post("/chat/stream")
async def chat_with_data_agent(query: str):

    async def event_generator():
        initial_state = {"query": query, "retry_count": 0}

        # 遍历 LangGraph 的每一个步骤
        async for output in data_agent.astream(initial_state):
            # 获取当前执行完的节点名称
            node_name = list(output.keys())[0]

            # 向前端推送过程状态（SSE 格式）
            if node_name == "retrieve_schema":
                yield f"data: {json.dumps({'status': '✅ 找到相关的业务表', 'detail': ''})}\n\n"
            elif node_name == "generate_sql":
                sql = output[node_name]["generated_sql"]
                yield f"data: {json.dumps({'status': '✅ SQL 编写完成', 'detail': sql})}\n\n"
            elif node_name == "execute_sql":
                if output[node_name].get("error_msg"):
                    yield f"data: {json.dumps({'status': '⚠️ 执行报错，正在重新思考...', 'detail': ''})}\n\n"
                else:
                    data = output[node_name]["execution_result"]
                    # 成功返回最终数据
                    yield f"data: {json.dumps({'status': '✅ 查数成功', 'data': data})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 四、 FastAPI 生产环境落地的三个“护栏”补充

既然是将代码部署到后端，必须防范以下问题：

#### 1. 数据库安全与性能护栏（绝对不能省）
*   **配置层**：FastAPI 配置的 DB Engine **必须是指向只读从库 (Read-Only Replica)**。如果是云端数据库，给 Agent 建一个专属账号，通过 GRANT 只赋予 SELECT 权限。
*   **代码层拦截**：如果你不放心，可以用 Python 库 `sqlglot`。在执行 `execute_sql_node` 之前，强行用 `sqlglot.parse` 解析 SQL，如果在 AST 语法树里发现任何 `DELETE` 或未加 `WHERE` 的查询，直接抛出异常，甚至不让它发往数据库请求。

#### 2. 返回结果的限制（大结果集截断）
如果运营的提问（如“查出所有用户的订单”）导致查询结果有 100 万行，直接在 `execute_sql_node` `fetchall()` 会把 FastAPI 的内存撑爆，导致 OOM 进程崩溃。
*   **策略**：在 Python 层面强制控制：`LIMIT 2000`。
*   如果执行的行数超过 `2000`，FastAPI 应该自动将结果转储成 CSV 文件存到 OSS/S3，然后在流式响应中返回：*“数据过大（15万条），已生成下载链接：http://oss.xxxx.com/xx.csv”*。

#### 3. Agent 异步化（防止阻塞其它接口）
FastAPI 的高性能基于异步（Asyncio）。但是如果我们在 `execute_sql_node` 中使用的是同步的 `SQLAlchemy`，或者做大批量的 RAG 检索，**会阻塞整个 FastAPI 事件循环**，导致其它运营打不开网页。
*   **策略**：确保大模型的请求使用 `ChatOpenAI.ainvoke` (异步调用)，或者将 Agent 放入 FastAPI 的后台任务执行环境（例如 `asyncio.to_thread` 或者集成 `Celery`）。

### 总结
上述方案搭建了一个骨架。其中难度最大的其实是 **第一步 `retrieve_schema_node` (找表节点)**。如果找错了表，后面所有的步骤全盘皆输。

你可以先不接入公司的真实数据库引擎和向量检索，按照上述架构，**用 SQLite 做一个有 3 张小表（如用户表、订单表、商品表）的 Demo 跑起来验证全流程**。当工作流（特别是重试机制）跑通后，再替换成公司的 MySQL/数仓和向量数据库。

觉得这个项目结构和流式推送的方案符合你们的设想吗？下一步可以深入聊聊“如何用 RAG 让大模型精准挑出正确的表”。
