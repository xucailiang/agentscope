# ReActAgent 工具调用完整流程说明

> 系统化说明 ReActAgent 的工具调用机制、执行流程和设计原理，涵盖流式/非流式、MCP/本地工具的统一处理

---

## 目录

- [一、架构概览](#一架构概览)
- [二、工具调用初始化](#二工具调用初始化)
- [三、统一调用机制](#三统一调用机制)
- [四、工具调用执行流程](#四工具调用执行流程)
- [五、流式与非流式处理](#五流式与非流式处理)
- [六、完整调用时序](#六完整调用时序)
- [七、设计要点与最佳实践](#七设计要点与最佳实践)

---

## 一、架构概览

### 1.1 核心组件

ReActAgent 的工具调用系统由以下核心组件组成：

```
┌─────────────────────────────────────────────────────────┐
│                     ReActAgent                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  推理循环 (Reasoning-Acting Loop)                 │  │
│  │  - 最多 max_iters 次迭代                          │  │
│  │  - 每次迭代: 推理 → 工具调用 → 检查完成           │  │
│  └──────────────────────────────────────────────────┘  │
│                           │                             │
│                           ▼                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Toolkit (工具集)                      │  │
│  │  - 统一管理所有工具（MCP/本地）                    │  │
│  │  - 提供统一调用接口                                │  │
│  │  - 支持工具分组和动态管理                          │  │
│  └──────────────────────────────────────────────────┘  │
│           │                           │                 │
│           ▼                           ▼                 │
│  ┌─────────────────┐        ┌─────────────────┐       │
│  │   MCP 工具      │        │   本地工具      │       │
│  │  (远程调用)     │        │  (函数调用)     │       │
│  └─────────────────┘        └─────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 设计原则

1. **统一接口**：MCP 工具和本地工具使用相同的调用方式
2. **异步优先**：所有工具调用都是异步的，支持并发执行
3. **流式兼容**：统一的异步生成器接口，同时支持流式和非流式
4. **可扩展性**：通过工具分组和钩子机制支持灵活扩展

### 1.3 关键数据流

```
用户消息
    ↓
推理 (LLM 生成工具调用)
    ↓
工具调用块 (ToolUseBlock)
    ↓
Toolkit 统一调用
    ↓
工具执行 (MCP/本地)
    ↓
工具响应 (ToolResponse)
    ↓
工具结果块 (ToolResultBlock)
    ↓
继续推理或返回最终响应
```

---

## 二、工具调用初始化

### 2.1 初始化流程

ReActAgent 在初始化时完成以下工具注册：

**必需工具**：
- `generate_response`: 结束对话的内置函数，将 LLM 的纯文本响应包装为工具调用

**可选工具**：
- **长期记忆工具**（当提供 `long_term_memory` 时）
  - `record_to_memory`: 记录信息到长期记忆
  - `retrieve_from_memory`: 从长期记忆检索信息

- **元工具**（当 `enable_meta_tool=True` 时）
  - `reset_equipped_tools`: 动态激活/停用工具组

- **计划工具**（当提供 `plan_notebook` 时）
  - 任务分解和管理相关工具

- **用户自定义工具**
  - 通过 `toolkit` 参数传入
  - 可以是本地 Python 函数或 MCP 工具

### 2.2 工具组织架构

**工具分组机制**：

| 分组类型 | 说明 | 激活策略 |
|---------|------|---------|
| `basic` | 基础工具组（默认） | 始终激活 |
| 自定义组 | 用户创建的工具组 | 按需激活 |

**工具注册方式对比**：

| 工具类型 | 注册方法 | 特点 |
|---------|---------|------|
| 本地函数 | `toolkit.register_tool_function(func)` | 直接调用 Python 函数 |
| MCP 工具 | `toolkit.register_mcp_client(client)` | 远程调用 MCP server |
| Pydantic 函数 | `toolkit.register_tool_function(func)` | 自动生成结构化输出 |

### 2.3 执行模式配置

**并行 vs 顺序执行**：

```
parallel_tool_calls = False (默认)
┌─────────┐    ┌─────────┐    ┌─────────┐
│ 工具 1  │ -> │ 工具 2  │ -> │ 工具 3  │
└─────────┘    └─────────┘    └─────────┘
  依次执行，总耗时 = 工具1 + 工具2 + 工具3

parallel_tool_calls = True
┌─────────┐
│ 工具 1  │
├─────────┤
│ 工具 2  │  同时执行
├─────────┤
│ 工具 3  │
└─────────┘
  并行执行，总耗时 ≈ max(工具1, 工具2, 工具3)
```

**循环次数限制**：

- `max_iters`: 控制推理-执行循环的最大次数（默认 10）
- 每次循环可能包含多个工具调用
- 防止无限循环，超过次数后强制总结

---

## 三、统一调用机制

### 3.1 设计目标

实现对 MCP 工具和本地函数的**无差别调用**，ReActAgent 无需知道工具来源。

### 3.2 统一调用架构

```
┌───────────────────────────────────────────────────────────┐
│                      Toolkit 层                            │
│                                                            │
│  所有工具统一存储为 RegisteredToolFunction                 │
│  {                                                         │
│    name: str,              // 工具名称                     │
│    original_func: Callable, // ⭐ 统一的可调用对象         │
│    json_schema: dict,      // JSON Schema                 │
│    group: str,             // 所属工具组                   │
│    preset_kwargs: dict,    // 预设参数                     │
│  }                                                         │
└───────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┴──────────────────┐
         │                                     │
    MCP 工具                                本地工具
         │                                     │
         ▼                                     ▼
┌──────────────────┐               ┌─────────────────┐
│ MCPToolFunction  │               │ Python 函数     │
│                  │               │                 │
│ async def        │               │ def/async def   │
│ __call__(**kw):  │               │ my_func(**kw):  │
│   调用 MCP server│               │   本地执行      │
│   返回 ToolResp  │               │   返回 ToolResp │
└──────────────────┘               └─────────────────┘
         │                                     │
         └─────────────────┬──────────────────┘
                           ▼
              统一返回 AsyncGenerator[ToolResponse]
```

### 3.3 MCP 工具转换机制

**关键转换点**：在注册 MCP 客户端时

```
步骤 1: 查询 MCP Server
   └─> await mcp_client.list_tools()
       返回: [Tool(name="search", schema={...}), ...]

步骤 2: 创建可调用包装
   └─> func = await mcp_client.get_callable_function("search")
       返回: MCPToolFunction 实例
       特点:
         - 实现 __call__ 方法，像普通函数一样调用
         - 内部通过 MCP 协议调用远程 server
         - 自动转换结果为 ToolResponse

步骤 3: 注册到 Toolkit
   └─> toolkit.register_tool_function(func)
       与本地函数使用相同的注册方法
```

### 3.4 统一调用流程

**从 ReActAgent 的视角**：

```
1. 获取工具调用块
   tool_call = {
     "type": "tool_use",
     "name": "search_place",  // 工具名
     "input": {"query": "北京天安门"}  // 参数
   }

2. 调用 Toolkit（不区分工具类型）
   tool_res = await toolkit.call_tool_function(tool_call)

3. Toolkit 内部处理
   a. 查找工具: tool_func = self.tools[tool_call["name"]]
   b. 合并参数: kwargs = {preset_kwargs, input}
   c. 执行工具: res = await tool_func.original_func(**kwargs)
   d. 包装结果: 统一返回 AsyncGenerator[ToolResponse]

4. ReActAgent 迭代结果（流式处理）
   async for chunk in tool_res:
       处理每个响应块
```

### 3.5 返回值统一包装

**所有工具的返回值都被包装为异步生成器**：

| 工具返回类型 | 包装方式 | 说明 |
|-------------|---------|------|
| `ToolResponse` | `_object_wrapper()` | 单个对象包装成生成器 |
| `AsyncGenerator` | 直接返回 | 已经是异步生成器 |
| `Generator` | `_sync_generator_wrapper()` | 同步生成器转异步 |

**优势**：
- ReActAgent 可以统一使用 `async for` 迭代
- 支持流式和非流式工具无缝切换
- 简化错误处理和中断机制

### 3.6 MCP vs 本地工具对比

| 维度 | MCP 工具 | 本地函数工具 | 是否统一 |
|------|---------|-------------|---------|
| **注册入口** | `register_mcp_client()` | `register_tool_function()` | ❌ |
| **内部存储** | `RegisteredToolFunction` | `RegisteredToolFunction` | ✅ |
| **JSON Schema** | 从 MCP server 获取 | 从函数签名解析 | ❌ 来源不同 |
| **调用方式** | `await tool_func(**kwargs)` | `await tool_func(**kwargs)` | ✅ |
| **返回格式** | `AsyncGenerator[ToolResponse]` | `AsyncGenerator[ToolResponse]` | ✅ |
| **ReActAgent 使用** | `toolkit.call_tool_function()` | `toolkit.call_tool_function()` | ✅ 完全相同 |

---

## 四、工具调用执行流程

### 4.1 推理-执行循环

**核心循环结构**：

```
for iteration in range(max_iters):

    1. 推理阶段 (_reasoning)
       ├─> 格式化提示（系统提示 + 记忆 + 提示消息）
       ├─> 调用 LLM
       ├─> 处理流式/非流式响应
       └─> 返回包含工具调用的消息

    2. 提取工具调用
       └─> tool_calls = msg.get_content_blocks("tool_use")

    3. 执行工具（_acting）
       ├─> 并行模式: asyncio.gather(*[_acting(tc) for tc in tool_calls])
       └─> 顺序模式: [await _acting(tc) for tc in tool_calls]

    4. 检查结束条件
       └─> 如果调用了 finish_function，退出循环

如果达到 max_iters 仍未完成:
    └─> 执行 _summarizing() 强制生成总结
```

### 4.2 推理阶段处理

**流式与非流式的分支**：

```
非流式推理:
  └─> res = await model(prompt, tools=schemas)
      └─> 一次性获得完整响应
      └─> 创建消息: Msg(name, res.content, role)
      └─> 打印: print(msg, last=True)

流式推理:
  └─> res = await model(prompt, tools=schemas)  // 返回异步生成器
      └─> msg = Msg(name, [], role)  // 创建空消息
      └─> async for chunk in res:
          ├─> msg.content = chunk.content  // 累积更新
          └─> print(msg, last=False)  // 标记为流式中间块
      └─> print(msg, last=True)  // 标记流式结束
```

**纯文本响应的自动包装**：

如果 LLM 返回纯文本（没有工具调用），自动转换为 `generate_response` 调用，确保统一处理流程。

### 4.3 工具执行阶段

**执行流程**：

```
1. 创建工具结果消息
   tool_res_msg = Msg("system", [ToolResultBlock(...)])

2. 调用工具
   tool_res = await toolkit.call_tool_function(tool_call)

3. 迭代处理结果（支持流式）
   async for chunk in tool_res:
       ├─> 更新输出: tool_res_msg.content[0]["output"] = chunk.content
       ├─> 判断是否打印（finish_function 成功时不打印）
       ├─> 检查中断信号
       └─> 提取 finish_function 的响应消息

4. 记录到内存
   await memory.add(tool_res_msg)
```

**finish_function 特殊处理**：

- **调用时**：转换为普通文本显示（通过 pre_print 钩子）
- **成功时**：不打印工具结果，直接返回响应消息
- **失败时**：打印错误信息，继续推理循环

### 4.4 内存记录机制

**完整的对话历史记录**：

```
[用户消息] 用户输入
    ↓
[推理消息] LLM 生成的工具调用
    ↓
[工具结果] 工具执行结果
    ↓
[推理消息] LLM 再次推理
    ↓
[工具结果] finish_function 结果
    ↓
[最终响应] 返回给用户的消息
```

**三个关键记录点**：
1. 推理消息：包含 LLM 生成的工具调用
2. 工具结果消息：每个工具的执行结果
3. 最终响应消息：返回给用户的完整回复

---

## 五、流式与非流式处理

### 5.1 核心区别

| 维度 | 非流式 | 流式 |
|------|--------|------|
| **配置** | `stream=False` | `stream=True` |
| **LLM 返回** | 单个 ChatResponse | AsyncGenerator[ChatResponse] |
| **内容特性** | 完整内容 | 累积式内容（每个 chunk 包含所有之前内容） |
| **消息创建** | `Msg(name, res.content, role)` | `Msg(name, [], role)` 后逐步更新 |
| **打印次数** | 1 次（last=True） | N+1 次（N 次 last=False + 1 次 last=True） |
| **用户体验** | 等待 → 完整显示 | 实时逐步显示 |

### 5.2 流式处理机制

**累积式更新**：

```
Chunk 1: content = [ToolUse(name="search", input={"q": "w"})]
Chunk 2: content = [ToolUse(name="search", input={"q": "weather"})]
Chunk 3: content = [ToolUse(name="search", input={"q": "weather today"})]

每个 chunk 都是完整的当前状态，无需手动拼接
```

**last 标志语义**：

```
last=False: 流式消息的中间 chunk
last=True:  流式消息的最后一个 chunk

注意: 一次 reply() 可能有多个 last=True
  - LLM 推理流式结束: last=True
  - 工具执行完成: last=True
  - 再次推理流式结束: last=True
  - 最终响应: last=True
```

### 5.3 消息队列机制

**生产者-消费者模式**：

```
生产者 (Agent.print):
  └─> await msg_queue.put((deepcopy(msg), last))

消费者 (stream_printing_messages):
  └─> async for msg, last in queue:
      └─> yield (msg, last)
```

**关键设计**：
- 使用 `deepcopy` 确保消息独立性
- 多个 Agent 可共享同一队列
- 通过结束信号标记任务完成

### 5.4 工具的流式支持

**非流式工具**：

```python
def search(query: str) -> ToolResponse:
    result = do_search(query)
    return ToolResponse(content=[...], is_last=True)

# Toolkit 自动包装为异步生成器
# 调用方只迭代一次
```

**流式工具**：

```python
async def search_streaming(query: str) -> AsyncGenerator[ToolResponse]:
    yield ToolResponse(content="搜索中...", is_last=False)
    results = await do_search(query)
    yield ToolResponse(content="找到结果...", is_last=False)
    yield ToolResponse(content=format(results), is_last=True)

# 调用方迭代多次，实时显示进度
```

### 5.5 适用场景对比

**非流式适用场景**：
- ✅ 地图查询、天气查询等结果较短的场景
- ✅ 批处理任务
- ✅ 快速响应要求
- ✅ 结果需要一次性处理

**流式适用场景**：
- ✅ 长文本生成（文章、代码）
- ✅ 需要实时反馈的交互场景
- ✅ Web 应用（SSE、WebSocket）
- ✅ 需要用户中断的长时间任务

---

## 六、完整调用时序

### 6.1 系统级时序图

```
用户
  │
  ├─> agent.reply(user_msg)
  │
  └─> ReActAgent
      │
      ├─> [准备阶段]
      │   ├─> memory.add(user_msg)
      │   ├─> 检索长期记忆（可选）
      │   └─> 检索知识库（可选）
      │
      └─> [推理-执行循环] (最多 max_iters 次)
          │
          ├─> _reasoning()
          │   ├─> 格式化提示
          │   ├─> model(prompt, tools)
          │   │   ├─> 非流式: 返回 ChatResponse
          │   │   └─> 流式: 返回 AsyncGenerator[ChatResponse]
          │   ├─> 处理响应（流式/非流式）
          │   └─> memory.add(reasoning_msg)
          │
          ├─> 提取工具调用
          │   └─> tool_calls = msg.get_content_blocks("tool_use")
          │
          ├─> 执行工具调用
          │   ├─> 并行: asyncio.gather(*[_acting(tc)])
          │   └─> 顺序: [await _acting(tc)]
          │       │
          │       └─> _acting(tool_call)
          │           ├─> toolkit.call_tool_function(tool_call)
          │           │   ├─> 查找工具: tools[name]
          │           │   ├─> 合并参数: kwargs
          │           │   ├─> 执行: await tool_func(**kwargs)
          │           │   │   ├─> MCP: 调用远程 server
          │           │   │   └─> 本地: 执行 Python 函数
          │           │   └─> 返回: AsyncGenerator[ToolResponse]
          │           │
          │           ├─> async for chunk in tool_res:
          │           │   ├─> 更新 tool_res_msg
          │           │   ├─> print(tool_res_msg, chunk.is_last)
          │           │   └─> 检查 finish_function
          │           │
          │           └─> memory.add(tool_res_msg)
          │
          └─> 检查结束条件
              ├─> 找到 reply_msg: break
              └─> 继续循环
      │
      ├─> [兜底处理]
      │   └─> if no reply_msg: _summarizing()
      │
      ├─> [后处理]
      │   ├─> 记录到长期记忆（可选）
      │   └─> memory.add(reply_msg)
      │
      └─> 返回 reply_msg
```

### 6.2 具体场景示例

**场景**：用户询问"北京天安门在哪里？"（使用高德地图 MCP）

```
T0: 用户输入
    └─> Msg("user", "北京天安门在哪里？", "user")

T1: 第 1 轮推理（流式）
    ├─> Chunk 1: [ToolUse(name="search_place", input={"q": "北"})]
    │   └─> print(msg, last=False)
    ├─> Chunk 2: [ToolUse(name="search_place", input={"q": "北京天安门"})]
    │   └─> print(msg, last=False)
    └─> Chunk 3: [完整的工具调用]
        └─> print(msg, last=True)

T2: 执行 search_place (MCP 工具)
    ├─> toolkit.call_tool_function(tool_call)
    ├─> MCPToolFunction.__call__(query="北京天安门")
    ├─> 调用高德地图 MCP server
    ├─> 返回结果: {"name": "天安门", "location": "..."}
    └─> ToolResponse(content=[结果], is_last=True)
        └─> print(tool_res_msg, last=True)

T3: 第 2 轮推理（流式）
    ├─> LLM 基于工具结果生成回复
    └─> 生成 generate_response 调用

T4: 执行 finish_function
    ├─> generate_response(response="天安门位于北京市东城区...")
    └─> 返回 response_msg
        └─> 退出循环

T5: 返回最终响应
    └─> Msg("agent", "天安门位于北京市东城区...", "assistant")
```

### 6.3 内存记录示例

```
[1] Msg(user, "北京天安门在哪里？", user)

[2] Msg(agent, [ToolUse(search_place, ...)], assistant)
    └─> 推理消息

[3] Msg(system, [ToolResult(search_place, output={...})], system)
    └─> 工具结果

[4] Msg(agent, [ToolUse(generate_response, ...)], assistant)
    └─> 再次推理

[5] Msg(system, [ToolResult(generate_response, ...)], system)
    └─> finish_function 结果

[6] Msg(agent, "天安门位于北京市东城区...", assistant)
    └─> 最终响应
```

---

## 七、设计要点与最佳实践

### 7.1 核心设计亮点

#### 1. 统一调用接口

**优势**：
- ReActAgent 无需关心工具来源（MCP/本地）
- 简化代码逻辑，降低维护成本
- 易于扩展新的工具类型

**实现机制**：
- 通过 `MCPToolFunction` 包装 MCP 工具为可调用对象
- 所有工具统一存储为 `RegisteredToolFunction`
- 统一返回 `AsyncGenerator[ToolResponse]`

#### 2. 异步生成器模式

**优势**：
- 同时支持流式和非流式工具
- 统一的迭代处理逻辑
- 便于实现中断和错误处理

**应用**：
- 非流式工具：包装为只迭代一次的生成器
- 流式工具：直接返回异步生成器
- 调用方：统一使用 `async for` 迭代

#### 3. 累积式内容更新

**优势**：
- 无需手动拼接内容
- 简化流式处理逻辑
- 每个 chunk 都是完整状态

**应用场景**：
- LLM 流式响应
- 流式工具输出
- 实时 UI 更新

#### 4. 完整的内存管理

**优势**：
- 可追溯完整的推理过程
- 支持多轮对话上下文
- 便于调试和分析

**记录内容**：
- 所有用户输入
- LLM 推理消息（包含工具调用）
- 所有工具执行结果
- 最终响应消息

#### 5. 灵活的钩子系统

**支持的钩子**：
- `pre_reasoning` / `post_reasoning`
- `pre_acting` / `post_acting`
- `pre_print` / `post_print`

**应用场景**：
- 自定义消息处理（如 finish_function 的显示转换）
- 工具调用监控和统计
- 自定义中断逻辑

### 7.2 最佳实践建议

#### 工具选择

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 地图查询 | MCP 工具 + 非流式 | 结果较短，一次性返回 |
| 文本生成 | 本地函数 + 流式 | 长文本，需要实时反馈 |
| 数据库查询 | 本地函数 + 非流式 | 快速响应，结果确定 |
| 复杂搜索 | MCP 工具 + 流式 | 远程调用，显示进度 |

#### 配置建议

**基础配置**：
```
max_iters = 10              # 防止无限循环
parallel_tool_calls = False  # 顺序执行，便于调试
stream = False              # 非流式，适合快速查询
```

**高性能配置**：
```
max_iters = 20              # 允许更多推理
parallel_tool_calls = True   # 并行执行，提高速度
stream = True               # 流式，实时反馈
```

**调试配置**：
```
max_iters = 3               # 限制循环次数
parallel_tool_calls = False  # 顺序执行，清晰日志
print_hint_msg = True       # 打印提示消息
```

#### 工具开发建议

**本地工具**：
- 优先使用累积式内容（简化调用方逻辑）
- 长时间运行的工具支持流式输出
- 使用 `ToolResponse.metadata` 传递额外信息
- 实现 `is_interrupted` 检测，支持中断

**MCP 工具**：
- 使用 `HttpStatelessClient` 简化连接管理
- 合理设置超时时间
- 考虑网络延迟，适当使用流式输出
- 实现错误处理和重试机制

#### 性能优化

**推理优化**：
- 合理设置 `max_iters`，避免过多循环
- 使用系统提示引导 LLM 减少工具调用次数
- 考虑使用 `tool_choice` 强制特定工具调用

**工具优化**：
- 批量调用时使用 `parallel_tool_calls=True`
- 合理使用工具分组，动态激活/停用
- 避免在循环中重复调用相同工具

**内存优化**：
- 长对话场景考虑定期清理内存
- 使用长期记忆存储重要信息
- 避免在内存中存储大文件

#### 错误处理

**工具调用失败**：
- Toolkit 自动捕获异常，返回错误信息
- LLM 可以基于错误信息重试或调整策略
- 考虑实现自定义错误处理钩子

**推理失败**：
- 达到 `max_iters` 时自动触发总结
- 可以通过钩子自定义兜底逻辑

**中断处理**：
- 流式模式下支持用户中断
- 自动为未完成的工具调用添加虚假结果
- 确保对话历史的一致性

### 7.3 调试与监控

#### 查看工具调用记录

```python
# 从内存中提取工具调用
memory = await agent.memory.get_memory()

tool_calls = []
for msg in memory:
    for tool_block in msg.get_content_blocks("tool_use"):
        tool_calls.append({
            "name": tool_block["name"],
            "input": tool_block["input"],
        })

print(f"共调用 {len(tool_calls)} 次工具")
```

#### 统计工具使用

```python
from collections import Counter

tool_counter = Counter(call["name"] for call in tool_calls)
for tool_name, count in tool_counter.items():
    print(f"{tool_name}: {count} 次")
```

#### 实时监控

```python
# 使用钩子监控工具调用
class ToolMonitor:
    def post_acting_hook(self, kwargs):
        tool_call = kwargs.get("tool_call")
        print(f"执行工具: {tool_call['name']}")
        return None

monitor = ToolMonitor()
agent.register_instance_hook("post_acting", "monitor", monitor.post_acting_hook)
```

### 7.4 常见问题与解决方案

#### Q1: 如何限制单次推理的工具调用数量？

**方案**：通过系统提示引导 + 钩子硬限制

```python
# 系统提示（软限制）
sys_prompt = "你是助手。规则：每次推理最多调用2个工具。"

# 钩子机制（硬限制）
def limit_tools_hook(self, kwargs):
    msg = kwargs["msg"]
    tools = msg.get_content_blocks("tool_use")
    if len(tools) > 2:
        msg.content = [b for b in msg.content
                      if b not in tools[2:]]
    return kwargs
```

#### Q2: MCP 工具和本地工具可以混用吗？

**答案**：完全可以，它们使用统一的调用接口。

```python
# 注册 MCP 工具
await toolkit.register_mcp_client(gaode_client)

# 注册本地工具
toolkit.register_tool_function(my_local_search)

# ReActAgent 可以无缝调用两者
```

#### Q3: 如何处理工具调用失败？

**答案**：Toolkit 自动将异常转换为错误消息，LLM 可以看到并调整策略。

```
工具执行失败
  └─> Toolkit 捕获异常
      └─> 返回 ToolResponse(content="Error: ...")
          └─> LLM 看到错误信息
              └─> 可以重试或使用其他工具
```

#### Q4: 流式模式下如何中断执行？

**答案**：通过 `asyncio.CancelledError` 机制。

```python
# 用户中断（如 Ctrl+C）
  └─> 触发 asyncio.CancelledError
      └─> 工具返回 is_interrupted=True
          └─> _acting 抛出 CancelledError
              └─> _reasoning 捕获并处理
                  └─> 为未完成的工具添加虚假结果
```

---

## 附录

### A. 相关源码文件

| 文件 | 说明 |
|------|------|
| `src/agentscope/agent/_react_agent.py` | ReActAgent 主实现 |
| `src/agentscope/tool/_toolkit.py` | Toolkit 工具管理 |
| `src/agentscope/mcp/_mcp_function.py` | MCP 工具包装 |
| `src/agentscope/message/_message_base.py` | 消息类型定义 |
| `src/agentscope/pipeline/_functional.py` | 流式消息管道 |

### B. 关键数据结构

**ToolUseBlock**：
```
{
  "type": "tool_use",
  "id": str,           // 工具调用 ID
  "name": str,         // 工具名称
  "input": dict,       // 工具参数
}
```

**ToolResultBlock**：
```
{
  "type": "tool_result",
  "id": str,           // 对应的工具调用 ID
  "name": str,         // 工具名称
  "output": str | List[ContentBlock],  // 工具输出
}
```

**ToolResponse**：
```
{
  "content": List[ContentBlock],  // 响应内容
  "metadata": dict,               // 元数据
  "is_last": bool,                // 是否为最后一个 chunk
  "is_interrupted": bool,         // 是否被中断
}
```

### C. 术语表

| 术语 | 说明 |
|------|------|
| **ReAct** | Reasoning and Acting，推理与执行循环模式 |
| **MCP** | Model Context Protocol，模型上下文协议 |
| **Toolkit** | 工具集，统一管理和调用工具 |
| **ToolUseBlock** | 工具调用块，LLM 生成的工具调用请求 |
| **ToolResultBlock** | 工具结果块，工具执行的返回结果 |
| **ToolResponse** | 工具响应对象，标准化的工具返回格式 |
| **finish_function** | 结束函数，用于返回最终响应 |
| **累积式内容** | 每个 chunk 包含完整当前状态的内容更新方式 |

---

**文档版本**: v2.0
**更新日期**: 2025-11-06
**适用版本**: AgentScope v0.1.0+
**维护者**: AgentScope Team
