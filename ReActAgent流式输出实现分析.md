# ReActAgent流式输出实现分析

## 1. 整体架构

ReActAgent的流式输出主要涉及三个核心组件：
- **模型层流式输出** (`ChatModelBase`)
- **智能体打印机制** (`AgentBase.print()`)
- **流式消息管道** (`stream_printing_messages()`)

## 2. 核心实现流程

### 2.1 模型层的流式返回

在模型配置中启用流式输出：

```python
model=DashScopeChatModel(
    api_key=os.environ.get("DASHSCOPE_API_KEY"),
    model_name="qwen-max",
    enable_thinking=False,
    stream=True,  # 启用流式输出
)
```

模型启用`stream=True`后，会返回一个**异步生成器**，每次迭代返回一个`ChatResponse`对象，内容是**累积式**的（当前chunk包含所有之前的内容）。

### 2.2 ReActAgent的_reasoning方法处理流式响应

关键代码在`src/agentscope/agent/_react_agent.py`的`_reasoning`方法中（第392-405行）：

```python
try:
    if self.model.stream:
        # 流式模式
        msg = Msg(self.name, [], "assistant")
        async for content_chunk in res:
            msg.content = content_chunk.content
            await self.print(msg, False)  # last=False 表示不是最后一个chunk
        await self.print(msg, True)  # last=True 表示流式消息结束

        # 添加一个微小的sleep以确保最后一个消息被正确放入队列
        await asyncio.sleep(0.001)

    else:
        # 非流式模式
        msg = Msg(self.name, list(res.content), "assistant")
        await self.print(msg, True)
```

**实现要点：**
- 检测`self.model.stream`来判断是否使用流式模式
- 流式模式下，遍历异步生成器`res`
- 每次迭代调用`await self.print(msg, False)`，其中`last=False`表示不是最后一个chunk
- 所有chunk完成后，调用`await self.print(msg, True)`标记流式消息结束
- 最后添加微小延迟确保消息正确入队

### 2.3 AgentBase的print方法

位于`src/agentscope/agent/_agent_base.py`（第198-209行）：

```python
async def print(self, msg: Msg, last: bool = True) -> None:
    """The function to display the message.

    Args:
        msg (`Msg`):
            The message object to be printed.
        last (`bool`, defaults to `True`):
            Whether this is the last one in streaming messages. For
            non-streaming message, this should always be `True`.
    """
    if not self._disable_msg_queue:
        await self.msg_queue.put((deepcopy(msg), last))

    if self._disable_console_output:
        return

    # 处理控制台输出...
```

**关键机制：**
- `print`方法将消息放入`msg_queue`队列
- 消息格式为元组：`(msg, last)`，其中`last`标记是否为流式消息的最后一个chunk
- 使用`deepcopy`确保消息的独立性
- 支持通过`_disable_console_output`控制是否在终端打印
- 支持通过`_disable_msg_queue`控制是否启用消息队列

### 2.4 stream_printing_messages管道

位于`src/agentscope/pipeline/_functional.py`（第107-169行）：

```python
async def stream_printing_messages(
    agents: list[AgentBase],
    coroutine_task: Coroutine,
    end_signal: str = "[END]",
) -> AsyncGenerator[Tuple[Msg, bool], None]:
    """将智能体在回复过程中打印的消息转换为异步生成器。

    注意：
    - 返回的布尔值表示该消息是否为一组流式消息中的最后一个chunk
    - 不是整个智能体调用的最后一条消息
    - 相同id的消息被视为同一条消息的不同chunk
    """

    # 为所有智能体启用消息队列
    queue = asyncio.Queue()
    for agent in agents:
        agent.set_msg_queue_enabled(True, queue)

    # 异步执行智能体任务
    task = asyncio.create_task(coroutine_task)

    # 设置任务完成回调，发送结束信号
    if task.done():
        await queue.put(end_signal)
    else:
        task.add_done_callback(lambda _: queue.put_nowait(end_signal))

    # 从队列中持续获取消息并yield
    while True:
        printing_msg = await queue.get()

        # 收到结束信号时退出
        if isinstance(printing_msg, str) and printing_msg == end_signal:
            break

        yield printing_msg
```

**工作流程：**
1. 创建一个`asyncio.Queue`队列
2. 为所有agent启用消息队列（指向同一个队列实例）
3. 异步执行智能体任务（`asyncio.create_task`）
4. 从队列中持续获取消息并yield给调用者
5. 当任务完成时，通过回调发送结束信号
6. 收到结束信号后退出循环

## 3. 完整使用示例

### 3.1 单智能体流式输出示例

参考 `examples/functionality/stream_printing_messages/single_agent.py`：

```python
import asyncio
import os
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_shell_command


async def main() -> None:
    """主函数"""
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_shell_command)

    agent = ReActAgent(
        name="Friday",
        sys_prompt="You are a helpful assistant named Friday.",
        model=DashScopeChatModel(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            model_name="qwen-max",
            enable_thinking=False,
            stream=True,  # 关键：启用流式输出
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    user_msg = Msg("user", "Hi! Who are you?", "user")

    # 关闭终端打印以避免输出混乱
    agent.set_console_output_enabled(False)

    # 以流式方式获取智能体的打印消息
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(user_msg),
    ):
        print(msg, last)


asyncio.run(main())
```

### 3.2 多智能体流式输出示例

参考 `examples/functionality/stream_printing_messages/multi_agent.py`：

```python
import asyncio
from agentscope.pipeline import MsgHub, stream_printing_messages


async def workflow(alice, bob, charlie):
    """多智能体工作流"""
    async with MsgHub(
        participants=[alice, bob, charlie],
        announcement=Msg("user", "Welcome! Let's meet each other.", "user"),
    ):
        await alice()
        await bob()
        await charlie()


async def main():
    # 创建多个智能体...
    alice, bob, charlie = [create_agent(_) for _ in ["Alice", "Bob", "Charlie"]]

    # 从多个智能体收集流式消息
    async for msg, last in stream_printing_messages(
        agents=[alice, bob, charlie],
        coroutine_task=workflow(alice, bob, charlie),
    ):
        print(msg, last)


asyncio.run(main())
```

## 4. 设计亮点

### 4.1 累积式内容
每个chunk包含所有之前的内容加上新内容，不需要手动拼接：

```python
# 模型返回的每个chunk都是累积的
# chunk1.content = "Hello"
# chunk2.content = "Hello world"
# chunk3.content = "Hello world!"
```

### 4.2 异步队列机制
使用`asyncio.Queue`实现生产者-消费者模式：
- **生产者**：智能体的`print`方法将消息放入队列
- **消费者**：`stream_printing_messages`从队列中取出消息并yield

### 4.3 last标志的语义
- `last=False`：当前消息是流式消息的中间chunk
- `last=True`：当前消息是流式消息的最后一个chunk（但不一定是智能体的最后一条消息）

### 4.4 灵活的控制选项

```python
# 控制终端输出
agent.set_console_output_enabled(False)  # 禁用终端打印

# 控制消息队列
agent.set_msg_queue_enabled(True, queue)  # 启用消息队列
```

### 4.5 工具调用的流式支持

在`_acting`方法中也支持流式工具响应（第482-498行）：

```python
# 工具函数也可以返回异步生成器实现流式输出
async for chunk in tool_res:
    # 更新工具结果消息的内容
    tool_res_msg.content[0]["output"] = chunk.content

    # 打印工具执行的中间结果
    if tool_call["name"] != self.finish_function_name:
        await self.print(tool_res_msg, chunk.is_last)
```

## 5. 流式输出的典型应用场景

### 5.1 实时反馈
用户可以立即看到智能体的思考过程和执行步骤，提升用户体验。

### 5.2 可中断性
配合AgentScope的中断机制，可以在流式输出时中断智能体执行：

```python
# 用户可以通过Ctrl+C或调用agent.interrupt()中断流式输出
try:
    async for msg, last in stream_printing_messages(agents=[agent], ...):
        print(msg)
except asyncio.CancelledError:
    print("用户中断了执行")
```

### 5.3 Web应用集成
可以轻松将流式输出集成到Web应用：

```python
# FastAPI示例
@app.post("/chat/stream")
async def chat_stream(message: str):
    async def event_generator():
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(Msg("user", message, "user")),
        ):
            yield {
                "data": json.dumps({
                    "content": msg.get_text_content(),
                    "is_last": last
                })
            }

    return EventSourceResponse(event_generator())
```

## 6. 技术要点总结

| 组件 | 职责 | 关键技术 |
|------|------|----------|
| **Model** | 生成流式内容 | 异步生成器、累积式内容 |
| **ReActAgent._reasoning** | 处理流式响应 | 异步迭代、调用print方法 |
| **AgentBase.print** | 分发消息 | 异步队列、deepcopy |
| **stream_printing_messages** | 收集并转发消息 | 异步生成器、队列消费 |

## 7. 与docs示例的对应关系

在`docs/tutorial/zh_CN/src/task_pipeline.py`（第217-246行）中有流式输出的文档示例：

```python
async def run_example_pipeline() -> None:
    """运行流式打印消息的示例。"""
    agent = create_agent("Alice", 20, "student")

    # 关闭agent的终端打印以避免输出混乱
    agent.set_console_output_enabled(False)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(
            Msg("user", "你好，你是谁？", "user"),
        ),
    ):
        print(msg, last)
        if last:
            print()  # 在每组流式消息结束后打印空行
```

## 8. 相关源码文件

- `src/agentscope/agent/_react_agent.py` - ReActAgent的主要实现
- `src/agentscope/agent/_agent_base.py` - AgentBase基类，提供print方法
- `src/agentscope/pipeline/_functional.py` - stream_printing_messages实现
- `examples/functionality/stream_printing_messages/` - 流式输出示例
- `docs/tutorial/zh_CN/src/task_pipeline.py` - 文档示例

---

**总结**：ReActAgent的流式输出通过**模型流式API** + **异步队列** + **生成器模式**实现了优雅的流式消息传递机制，既支持实时反馈，又保持了代码的清晰性和可扩展性。

