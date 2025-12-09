# 高德地图 MCP Server 与 ReActAgent 集成指南

## 📋 目录

- [简介](#简介)
- [核心概念](#核心概念)
- [快速开始](#快速开始)
- [详细说明](#详细说明)
- [完整示例](#完整示例)
- [常见问题](#常见问题)

---

## 简介

本指南展示如何将**高德地图 MCP Server** 集成到 **ReActAgent** 中，使用**非流式模式**获取地图服务结果。

### 什么是 MCP？

MCP (Model Context Protocol) 是一个标准协议，允许 AI 应用与外部工具和服务进行通信。

### 高德地图 MCP Server

高德地图提供了 MCP 接口，支持：
- 地点搜索
- 路线规划
- POI 查询
- 地理编码
- 等地图服务

---

## 核心概念

### 1. HttpStatelessClient vs HttpStatefulClient

| 特性 | HttpStatelessClient | HttpStatefulClient |
|------|---------------------|-------------------|
| **连接管理** | 无需连接 | 需要 connect/close |
| **状态保持** | 每次请求独立 | 保持会话状态 |
| **使用场景** | 简单 API 调用 | 需要会话上下文 |
| **代码复杂度** | 简单 | 稍复杂 |

**高德地图 MCP 推荐使用 `HttpStatelessClient`**，因为地图 API 通常是无状态的。

### 2. 流式 vs 非流式

| 模式 | 配置 | 特点 | 适用场景 |
|------|------|------|---------|
| **非流式** | `stream=False` | 一次性返回完整结果 | 快速查询、批处理 |
| **流式** | `stream=True` | 逐步返回结果 | 长文本生成、实时反馈 |

**地图查询推荐使用非流式模式**，因为结果通常较短，一次性返回即可。

---

## 快速开始

### 环境准备

```bash
# 1. 安装 AgentScope
pip install agentscope

# 2. 设置环境变量
export GAODE_API_KEY="你的高德地图API密钥"
export DASHSCOPE_API_KEY="你的阿里云API密钥"
```

### 最简示例（3 步集成）

```python
import asyncio
import os
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.mcp import HttpStatelessClient
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit


async def main():
    # 步骤 1: 创建 MCP 客户端
    gaode_client = HttpStatelessClient(
        name="gaode_map",
        transport="streamable_http",
        url=f"https://mcp.amap.com/mcp?key={os.environ['GAODE_API_KEY']}",
    )

    # 步骤 2: 注册到 Toolkit
    toolkit = Toolkit()
    await toolkit.register_mcp_client(gaode_client)

    # 步骤 3: 创建 Agent（非流式）
    agent = ReActAgent(
        name="地图助手",
        sys_prompt="你是一个地图查询助手。",
        model=DashScopeChatModel(
            model_name="qwen-max",
            stream=False,  # 非流式模式
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    # 使用 Agent
    response = await agent(Msg("user", "北京天安门在哪里？", "user"))
    print(response.content)


asyncio.run(main())
```

### 运行示例

```bash
# 运行最简示例
python gaode_mcp_simple.py

# 运行完整示例
python gaode_mcp_example.py
```

---

## 详细说明

### 1. 创建 MCP 客户端

```python
from agentscope.mcp import HttpStatelessClient

gaode_client = HttpStatelessClient(
    # 必需参数
    name="gaode_map",              # MCP 客户端名称（自定义）
    transport="streamable_http",   # 传输协议（高德使用 streamable_http）
    url=f"https://mcp.amap.com/mcp?key={api_key}",  # MCP 端点 URL
)
```

**参数说明**：

- `name`: 客户端标识符，用于日志和调试
- `transport`: 传输协议
  - `"streamable_http"`: HTTP 流式传输（推荐）
  - `"sse"`: Server-Sent Events
- `url`: MCP 服务端点
  - 高德地图：`https://mcp.amap.com/mcp?key={YOUR_KEY}`
  - 注意：URL 中包含 API Key

**无状态客户端优势**：

- ✅ 无需调用 `connect()` 和 `close()`
- ✅ 代码更简洁
- ✅ 适合单次请求场景
- ✅ 自动处理连接管理

### 2. 注册 MCP 工具

```python
from agentscope.tool import Toolkit

toolkit = Toolkit()
await toolkit.register_mcp_client(gaode_client)
```

**注册后发生了什么**？

1. `register_mcp_client()` 会查询 MCP server 的所有可用工具
2. 将每个工具转换为 AgentScope 的工具函数
3. 添加到 Toolkit，供 Agent 使用

**查看已注册的工具**：

```python
tool_schemas = toolkit.get_json_schemas()
for schema in tool_schemas:
    tool_name = schema["function"]["name"]
    tool_desc = schema["function"]["description"]
    print(f"{tool_name}: {tool_desc}")
```

### 3. 创建 ReActAgent（非流式）

```python
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel

agent = ReActAgent(
    name="地图助手",
    sys_prompt="你是一个地图查询助手，使用高德地图工具回答用户问题。",
    model=DashScopeChatModel(
        model_name="qwen-max",
        api_key=os.environ["DASHSCOPE_API_KEY"],
        stream=False,  # ⭐ 关键：非流式模式
    ),
    formatter=DashScopeChatFormatter(),
    toolkit=toolkit,
    parallel_tool_calls=False,  # 顺序执行工具（可选）
    max_iters=10,               # 最大推理次数（可选）
)
```

**关键配置**：

- `stream=False`: 非流式模式
  - LLM 一次性返回完整响应
  - 工具调用结果一次性返回
  - 适合快速查询场景

- `parallel_tool_calls=False`: 顺序执行
  - 如果 LLM 生成多个工具调用，按顺序执行
  - 设置为 `True` 可并行执行（提高速度）

- `max_iters=10`: 最大循环次数
  - 防止无限循环
  - 超过次数后强制总结并返回

### 4. 调用 Agent

#### 基础调用

```python
from agentscope.message import Msg

response = await agent(Msg("user", "北京故宫在哪里？", "user"))
print(response.content)
```

#### 使用 reply 方法

```python
response = await agent.reply(Msg("user", "查询上海东方明珠", "user"))
print(response.content)
```

#### 结构化输出

```python
from pydantic import BaseModel, Field

class LocationInfo(BaseModel):
    name: str = Field(description="地点名称")
    address: str = Field(description="详细地址")
    location: str = Field(description="经纬度")

response = await agent.reply(
    msg=Msg("user", "上海东方明珠的信息", "user"),
    structured_model=LocationInfo,
)

print(response.content)         # 文本响应
print(response.metadata)        # 结构化数据
```

### 5. 直接调用 MCP 工具

不通过 Agent，直接调用 MCP 工具：

```python
# 获取可调用的工具函数
search_tool = await gaode_client.get_callable_function(
    "search_place",           # 工具名称
    wrap_tool_result=True,    # 包装为 ToolResponse
)

# 直接调用
result = await search_tool(query="北京天安门")
print(result)
```

---

## 完整示例

### 示例 1: 地点搜索

```python
import asyncio
import os
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.mcp import HttpStatelessClient
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit


async def search_place_example():
    """地点搜索示例"""

    # 创建 MCP 客户端
    gaode_client = HttpStatelessClient(
        name="gaode_map",
        transport="streamable_http",
        url=f"https://mcp.amap.com/mcp?key={os.environ['GAODE_API_KEY']}",
    )

    # 注册工具
    toolkit = Toolkit()
    await toolkit.register_mcp_client(gaode_client)

    # 创建 Agent
    agent = ReActAgent(
        name="MapBot",
        sys_prompt=(
            "你是一个地图助手。当用户询问地点时，使用高德地图工具查询，"
            "并以友好的方式回答用户。"
        ),
        model=DashScopeChatModel(
            model_name="qwen-max",
            stream=False,
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    # 查询地点
    queries = [
        "北京故宫博物院在哪里？",
        "上海迪士尼乐园的地址",
        "广州塔的位置信息",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"用户: {query}")
        print(f"{'='*60}")

        response = await agent(Msg("user", query, "user"))
        print(f"\nAgent: {response.content}")


asyncio.run(search_place_example())
```

### 示例 2: 结构化输出

```python
import asyncio
import json
import os
from pydantic import BaseModel, Field
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.mcp import HttpStatelessClient
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit


class POIInfo(BaseModel):
    """POI 信息模型"""
    name: str = Field(description="地点名称")
    address: str = Field(description="详细地址")
    longitude: float = Field(description="经度")
    latitude: float = Field(description="纬度")
    phone: str = Field(default="", description="联系电话")


async def structured_output_example():
    """结构化输出示例"""

    # 创建 Agent（省略重复代码）
    gaode_client = HttpStatelessClient(
        name="gaode_map",
        transport="streamable_http",
        url=f"https://mcp.amap.com/mcp?key={os.environ['GAODE_API_KEY']}",
    )

    toolkit = Toolkit()
    await toolkit.register_mcp_client(gaode_client)

    agent = ReActAgent(
        name="POIBot",
        sys_prompt="你是一个 POI 查询助手，提供结构化的地点信息。",
        model=DashScopeChatModel(model_name="qwen-max", stream=False),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    # 查询并获取结构化输出
    response = await agent.reply(
        msg=Msg("user", "查询北京天坛公园的详细信息", "user"),
        structured_model=POIInfo,
    )

    print("文本响应:")
    print(response.content)

    print("\n结构化数据:")
    print(json.dumps(response.metadata, indent=2, ensure_ascii=False))


asyncio.run(structured_output_example())
```

### 示例 3: 多轮对话

```python
async def multi_turn_conversation():
    """多轮对话示例"""

    # 创建 Agent（省略重复代码）
    gaode_client = HttpStatelessClient(
        name="gaode_map",
        transport="streamable_http",
        url=f"https://mcp.amap.com/mcp?key={os.environ['GAODE_API_KEY']}",
    )

    toolkit = Toolkit()
    await toolkit.register_mcp_client(gaode_client)

    agent = ReActAgent(
        name="TravelBot",
        sys_prompt="你是一个旅行助手，帮助用户规划行程。",
        model=DashScopeChatModel(model_name="qwen-max", stream=False),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    # 多轮对话
    conversation = [
        "我想去北京旅游，有什么推荐的景点吗？",
        "故宫怎么走？",
        "附近有什么好吃的餐厅？",
    ]

    for user_input in conversation:
        print(f"\n用户: {user_input}")
        response = await agent(Msg("user", user_input, "user"))
        print(f"Agent: {response.content}")


asyncio.run(multi_turn_conversation())
```

---

## 常见问题

### Q1: 无状态客户端和有状态客户端的区别？

**A**:

| 特性 | HttpStatelessClient | HttpStatefulClient |
|------|---------------------|-------------------|
| 连接管理 | 自动管理，无需手动 connect/close | 需要手动 `await client.connect()` 和 `await client.close()` |
| 会话保持 | 每次请求独立 | 保持会话状态 |
| 使用场景 | 简单 API 调用（推荐） | 需要会话上下文的复杂交互 |

**示例对比**：

```python
# 无状态客户端（推荐，更简单）
gaode_client = HttpStatelessClient(...)
await toolkit.register_mcp_client(gaode_client)
# 无需 connect 和 close

# 有状态客户端
gaode_client = HttpStatefulClient(...)
await gaode_client.connect()  # 必须先连接
await toolkit.register_mcp_client(gaode_client)
# ... 使用 ...
await gaode_client.close()    # 必须手动关闭
```

### Q2: 如何查看 MCP Server 提供了哪些工具？

**A**:

```python
toolkit = Toolkit()
await toolkit.register_mcp_client(gaode_client)

# 获取所有工具的 JSON Schema
tool_schemas = toolkit.get_json_schemas()

for schema in tool_schemas:
    function_info = schema.get("function", {})
    print(f"工具名: {function_info.get('name')}")
    print(f"描述: {function_info.get('description')}")
    print(f"参数: {function_info.get('parameters')}")
    print("-" * 40)
```

### Q3: 非流式和流式如何选择？

**A**:

**使用非流式（`stream=False`）**：
- ✅ 地图查询（结果较短）
- ✅ 快速响应场景
- ✅ 批处理任务
- ✅ 结果需要一次性处理

**使用流式（`stream=True`）**：
- ✅ 长文本生成
- ✅ 需要实时反馈
- ✅ Web 应用（SSE、WebSocket）
- ✅ 可能需要用户中断

**地图查询推荐：非流式模式**

### Q4: 如何处理错误？

**A**:

```python
try:
    response = await agent(Msg("user", "查询北京天安门", "user"))
    print(response.content)
except Exception as e:
    print(f"错误: {e}")
    # 处理错误
```

### Q5: 如何设置超时时间？

**A**:

```python
# 在模型配置中设置超时
agent = ReActAgent(
    name="MapBot",
    model=DashScopeChatModel(
        model_name="qwen-max",
        stream=False,
        timeout=30,  # 30 秒超时
    ),
    # ...
)
```

### Q6: 如何启用并行工具调用？

**A**:

```python
agent = ReActAgent(
    # ...
    parallel_tool_calls=True,  # 启用并行执行
)

# 当 LLM 生成多个工具调用时，会同时执行
# 例如: 同时查询多个地点的信息
```

### Q7: 如何查看 Agent 的执行过程？

**A**:

```python
# 查看对话历史
memory_msgs = await agent.memory.get_memory()

for msg in memory_msgs:
    print(f"{msg.name} ({msg.role}): {msg.content}")
```

或者使用流式管道查看实时过程（即使模型是非流式）：

```python
from agentscope.pipeline import stream_printing_messages

agent.set_console_output_enabled(False)

async for msg, last in stream_printing_messages(
    agents=[agent],
    coroutine_task=agent(Msg("user", "查询故宫", "user")),
):
    print(f"[{'FINAL' if last else 'CHUNK'}] {msg.get_text_content()}")
```

---

## 进阶技巧

### 1. 自定义系统提示

```python
agent = ReActAgent(
    name="MapExpert",
    sys_prompt=(
        "你是一个专业的地理信息专家。"
        "当用户询问地点时，你应该："
        "1. 使用高德地图工具查询准确信息"
        "2. 提供详细的地址和坐标"
        "3. 如果有多个结果，列出主要的几个"
        "4. 用友好、专业的语气回答"
    ),
    # ...
)
```

### 2. 结合长期记忆

```python
from agentscope.memory import LongTermMemoryBase

agent = ReActAgent(
    # ...
    long_term_memory=your_long_term_memory,
    long_term_memory_mode="both",  # agent_control/static_control/both
)
```

### 3. 结合知识库

```python
from agentscope.rag import KnowledgeBase

kb = KnowledgeBase(...)

agent = ReActAgent(
    # ...
    knowledge=[kb],
    enable_rewrite_query=True,  # 启用查询重写
)
```

---

## 总结

### 核心步骤

1. **创建 MCP 客户端**: `HttpStatelessClient`
2. **注册到 Toolkit**: `await toolkit.register_mcp_client(client)`
3. **创建 Agent**: 配置 `stream=False`
4. **调用 Agent**: `await agent(msg)`

### 最佳实践

- ✅ 使用 `HttpStatelessClient` 简化代码
- ✅ 地图查询使用非流式模式
- ✅ 编写清晰的系统提示
- ✅ 使用结构化输出获取规范数据
- ✅ 合理设置 `max_iters` 避免无限循环

### 相关文档

- [AgentScope 官方文档](https://doc.agentscope.io)
- [ReActAgent 工具调用完整流程](./ReActAgent工具调用完整流程.md)
- [MCP 官方规范](https://modelcontextprotocol.io)

---

**文档版本**: v1.0
**创建日期**: 2025-11-06
**适用版本**: AgentScope v0.1.0+

