# AgentScope RAG 模块完整说明

## 目录
- [一、核心组件架构](#一核心组件架构)
- [二、完整的使用流程](#二完整的使用流程)
- [三、高级用法：集成到 Agent](#三高级用法集成到-agent)
- [四、多模态 RAG](#四多模态-rag)
- [五、设计亮点](#五设计亮点)
- [六、示例代码](#六示例代码)

---

## 一、核心组件架构

RAG 模块采用了清晰的**分层架构设计**，主要包含以下四个核心组件：

### 1. Document（文档对象）📄

**位置**: `src/agentscope/rag/_document.py`

**核心类**:
- `Document`: 数据块对象，包含元数据、向量嵌入和相似度分数
- `DocMetadata`: 文档元数据，包含内容、文档ID、块ID和总块数

**数据结构**:
```python
@dataclass
class DocMetadata(DictMixin):
    content: TextBlock | ImageBlock | VideoBlock  # 数据内容
    doc_id: str                                    # 文档ID
    chunk_id: int                                  # 块ID
    total_chunks: int                              # 总块数

@dataclass
class Document:
    metadata: DocMetadata      # 元数据
    id: str                    # 唯一标识符
    embedding: Embedding       # 向量嵌入（添加到知识库时填充）
    score: float              # 相似度分数（检索时填充）
```

### 2. Reader（文档读取器）📖

**位置**: `src/agentscope/rag/_reader/`

**作用**: 读取原始数据并将其切分成文档块

**支持的读取器**:

| 读取器 | 说明 | 支持格式 |
|--------|------|----------|
| `TextReader` | 读取文本并按字符/句子/段落切分 | 字符串、文本文件 |
| `PDFReader` | 读取PDF文件，提取文本后切分 | PDF 文件 |
| `ImageReader` | 读取图像（用于多模态RAG） | 图像文件/URL |

**切分策略**:
- `split_by="char"`: 按字符数切分，适用于任意语言
- `split_by="sentence"`: 按句子切分（使用 nltk），仅支持英文
- `split_by="paragraph"`: 按段落切分（按换行符分割）

**初始化参数**:
```python
reader = TextReader(
    chunk_size=512,           # 每块大小（字符数）
    split_by="sentence"       # 切分方式
)
```

### 3. VDBStore（向量数据库存储）💾

**位置**: `src/agentscope/rag/_store/`

**作用**: 存储和检索向量嵌入

**支持的向量数据库**:

| 存储类 | 说明 | 特点 |
|--------|------|------|
| `QdrantStore` | 基于 Qdrant 向量数据库 | 支持内存模式和持久化 |
| `MilvusLiteStore` | 基于 Milvus Lite 向量数据库 | 轻量级，易于部署 |

**核心方法**:
- `add(documents)`: 添加文档向量到数据库
- `search(query_embedding, limit, score_threshold)`: 向量相似度搜索
- `delete(ids, filter)`: 删除文档
- `get_client()`: 获取底层数据库客户端，访问完整功能

**初始化示例**:
```python
# Qdrant Store
store = QdrantStore(
    location=":memory:",              # ":memory:" 或文件路径
    collection_name="my_collection",
    dimensions=1024,                  # 向量维度
)

# Milvus Lite Store
store = MilvusLiteStore(
    uri="./milvus_demo.db",          # 本地文件或远程地址
    collection_name="my_collection",
    dimensions=1024,
    distance="COSINE",                # COSINE, L2, IP
)
```

### 4. KnowledgeBase（知识库）🧠

**位置**: `src/agentscope/rag/_knowledge_base.py` 和 `_simple_knowledge.py`

**作用**: 统一管理文档的添加和检索流程

**实现类**:
- `KnowledgeBase`: 抽象基类，定义接口规范
- `SimpleKnowledge`: 简单实现，支持基本的添加和检索功能

**核心方法**:
- `add_documents(documents)`: 将文档向量化并存储
- `retrieve(query, limit, score_threshold)`: 检索相关文档
- `retrieve_knowledge(query, limit, score_threshold)`: 封装好的工具函数，可直接提供给 Agent 使用

---

## 二、完整的使用流程

### 流程图

```
原始数据 
    ↓
Reader（切分文档）
    ↓
Document 列表
    ↓
Embedding Model（向量化）
    ↓
VDBStore（存储到向量数据库）
    ↓
查询检索（用户输入）
    ↓
向量相似度搜索
    ↓
返回相关文档
```

### 详细步骤

#### 步骤1: 创建 Reader 并读取文档

```python
from agentscope.rag import TextReader, PDFReader

# 创建文本读取器
reader = TextReader(
    chunk_size=1024,        # 每块大小（字符数）
    split_by="sentence"     # 按句子切分
)

# 读取文本（支持字符串或文件路径）
documents = await reader(
    text="Your text content here..."
)

# 或读取 PDF
pdf_reader = PDFReader(
    chunk_size=1024, 
    split_by="sentence"
)
pdf_documents = await pdf_reader(
    pdf_path="example.pdf"
)
```

**切分逻辑**:
1. **按字符**: 简单地按固定字符数切分
2. **按句子**: 使用 nltk.sent_tokenize() 识别句子边界
3. **按段落**: 按换行符 `\n` 分割

**生成的 Document 结构**:
- 每个 chunk 都有唯一的 `chunk_id`（从0开始）
- 所有来自同一文档的 chunks 共享相同的 `doc_id`（基于内容的 SHA256 hash）
- `total_chunks` 记录该文档的总块数

#### 步骤2: 创建知识库（向量数据库 + 向量模型）

```python
from agentscope.rag import SimpleKnowledge, QdrantStore
from agentscope.embedding import DashScopeTextEmbedding
import os

knowledge = SimpleKnowledge(
    # 向量数据库
    embedding_store=QdrantStore(
        location=":memory:",              # 内存模式，或使用文件路径持久化
        collection_name="my_collection",
        dimensions=1024,                  # 向量维度（需与embedding模型匹配）
    ),
    # 向量化模型
    embedding_model=DashScopeTextEmbedding(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        model_name="text-embedding-v4",
    ),
)
```

**注意事项**:
- `dimensions` 必须与 embedding 模型的输出维度一致
- 向量数据库可以选择内存模式（`:memory:`）或持久化到文件
- 可以使用不同的 embedding 模型（OpenAI, DashScope, 本地模型等）

#### 步骤3: 将文档添加到知识库（向量化 + 存储）

```python
# 添加文档到知识库
await knowledge.add_documents(documents)
```

**内部处理流程**:
1. **验证**: 检查文档类型是否与 embedding 模型支持的模态匹配
2. **向量化**: 批量调用 embedding 模型将文档内容转为向量
3. **存储**: 将向量和元数据存储到向量数据库

```python
# SimpleKnowledge.add_documents() 的核心逻辑
async def add_documents(self, documents):
    # 1. 验证文档类型
    for doc in documents:
        if doc.metadata.content["type"] not in self.embedding_model.supported_modalities:
            raise ValueError(f"Unsupported content type")
    
    # 2. 批量向量化
    res_embeddings = await self.embedding_model(
        [_.metadata.content for _ in documents]
    )
    
    # 3. 填充 embedding 字段
    for doc, embedding in zip(documents, res_embeddings.embeddings):
        doc.embedding = embedding
    
    # 4. 存储到向量数据库
    await self.embedding_store.add(documents)
```

#### 步骤4: 检索相关文档

```python
# 基础检索
docs = await knowledge.retrieve(
    query="What is the password?",
    limit=5,                    # 返回 top-5 结果
    score_threshold=0.7,        # 相似度阈值过滤（0-1之间）
)

# 遍历结果
for doc in docs:
    print(f"Score: {doc.score}")
    print(f"Content: {doc.metadata.content['text']}")
    print(f"Doc ID: {doc.metadata.doc_id}")
    print(f"Chunk: {doc.metadata.chunk_id}/{doc.metadata.total_chunks}")
```

**内部检索流程**:
1. **向量化查询**: 将查询文本转换为向量
2. **相似度搜索**: 在向量数据库中进行 KNN 搜索
3. **过滤**: 应用 `score_threshold` 过滤低相关性结果
4. **返回**: 返回 Document 列表，包含相似度分数

**相似度分数说明**:
- 使用的距离度量取决于向量数据库的配置（COSINE, L2, IP）
- 分数越高表示越相关
- `score_threshold` 可以动态调整以获取更多或更少的结果

---

## 三、高级用法：集成到 Agent

### 方式1: 作为工具函数（Agent主动调用）

这种方式让 Agent 根据需要**主动决定**是否调用 RAG 工具。

```python
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit

# 创建知识库
knowledge = SimpleKnowledge(...)
await knowledge.add_documents(documents)

# 创建工具集
toolkit = Toolkit()

# 将 retrieve_knowledge 注册为工具
toolkit.register_tool_function(
    knowledge.retrieve_knowledge,
    func_description=(
        "Retrieve relevant documents from the knowledge base. "
        "The `query` parameter is critical for retrieval quality. "
        "Try different queries to get the best results. "
        "Adjust `limit` and `score_threshold` to control result count."
    ),
)

# 创建 Agent 并提供工具
agent = ReActAgent(
    name="Friday",
    sys_prompt=(
        "You're a helpful assistant equipped with a "
        "'retrieve_knowledge' tool. Use it to find relevant information."
    ),
    toolkit=toolkit,
    model=DashScopeChatModel(...),
    formatter=DashScopeChatFormatter(),
)

# Agent 会自动决定何时调用 retrieve_knowledge
msg = await agent(Msg("user", "What is John's father's name?", "user"))
```

**优点**:
- 更灵活，Agent 可以动态决定检索策略
- 可以多次调用，尝试不同的查询参数

**缺点**:
- 需要更强大的 LLM 来管理检索过程
- 可能增加 token 消耗

### 方式2: 静态集成（ReActAgent 自动检索）

这种方式在每次 Agent 回复前**自动检索**相关信息。

```python
from agentscope.agent import ReActAgent

# 创建知识库
knowledge = SimpleKnowledge(...)
await knowledge.add_documents(documents)

# 直接传入 knowledge 参数
agent = ReActAgent(
    name="Friday",
    sys_prompt="You're a helpful assistant.",
    model=DashScopeChatModel(...),
    formatter=DashScopeChatFormatter(),
    knowledge=knowledge,  # 直接传入知识库
)

# Agent 在每次回复前会自动检索相关信息
msg = await agent(Msg("user", "Do you know my name?", "user"))
```

**优点**:
- 实现简单，无需管理工具调用
- 适合每次都需要检索的场景

**缺点**:
- 缺乏灵活性，每次都会检索
- 用户输入可能不够具体，导致检索质量下降

### 对比总结

| 特性 | 工具函数模式 | 静态集成模式 |
|------|--------------|--------------|
| 灵活性 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 实现难度 | ⭐⭐⭐ | ⭐ |
| LLM 要求 | 高 | 中 |
| Token 消耗 | 较高 | 较低 |
| 适用场景 | 复杂任务，需要多次检索 | 简单问答，每次都需要检索 |

---

## 四、多模态 RAG

AgentScope 支持**多模态 RAG**，可以存储和检索图像、视频等非文本数据。

### 基本用法

```python
from agentscope.rag import ImageReader, SimpleKnowledge, QdrantStore
from agentscope.embedding import DashScopeMultiModalEmbedding

# 1. 读取图像
reader = ImageReader()
docs = await reader(image_url="path/to/image.png")

# 也可以批量读取
docs = await reader(image_url=["image1.png", "image2.png", "image3.png"])

# 2. 创建多模态知识库
knowledge = SimpleKnowledge(
    embedding_model=DashScopeMultiModalEmbedding(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        model_name="multimodal-embedding-v1",
        dimensions=1024,
    ),
    embedding_store=QdrantStore(
        location=":memory:",
        collection_name="multimodal_collection",
        dimensions=1024,
    ),
)

# 3. 添加文档
await knowledge.add_documents(docs)

# 4. 检索（使用文本查询检索图像）
docs = await knowledge.retrieve(
    query="a person's name",
    limit=3,
    score_threshold=0.5,
)
```

### 与 VL Agent 结合

```python
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel

agent = ReActAgent(
    name="Friday",
    sys_prompt="You're a helpful assistant.",
    model=DashScopeChatModel(
        model_name="qwen3-vl-plus",  # 视觉语言模型
    ),
    knowledge=knowledge,  # 多模态知识库
)

# Agent 可以检索图像并理解其内容
await agent(Msg("user", "Do you know my name?", "user"))
```

### 支持的内容类型

| 内容类型 | Block 类 | Embedding 模型要求 |
|----------|----------|-------------------|
| 文本 | `TextBlock` | 文本 embedding 模型 |
| 图像 | `ImageBlock` | 多模态 embedding 模型 |
| 视频 | `VideoBlock` | 多模态 embedding 模型 |

---

## 五、设计亮点

### 1. 解耦设计 🎯

四层架构（Reader → Document → Store → KnowledgeBase）完全解耦：
- 可以自由组合不同的 Reader、Store 和 Embedding 模型
- 易于扩展新的组件（例如添加新的向量数据库支持）

### 2. 多种存储后端 💾

支持多种向量数据库，可以根据需求选择：
- **Qdrant**: 适合生产环境，性能优秀
- **Milvus Lite**: 轻量级，易于部署和测试

### 3. 多模态支持 🎨

原生支持文本、图像等多种数据类型：
- 统一的 Document 接口
- 自动处理不同模态的 embedding

### 4. 灵活切分策略 ✂️

支持多种文本切分方式：
- 按字符：适用于所有语言
- 按句子：适用于英文，保持语义完整性
- 按段落：适用于结构化文档

### 5. 统一接口 🔌

所有组件都实现抽象基类：
- `ReaderBase`: 定义 Reader 接口
- `VDBStoreBase`: 定义 Store 接口
- `KnowledgeBase`: 定义知识库接口

保证了接口一致性，降低学习成本。

### 6. 异步设计 ⚡

全流程使用 async/await：
- 提高 I/O 密集型操作的性能
- 支持并发处理多个请求

### 7. 双集成模式 🔧

提供两种集成方式：
- **工具模式**: Agent 主动调用，更灵活
- **静态模式**: 自动检索，更简单

满足不同场景的需求。

### 8. 可扩展性 📈

- 可以轻松添加新的 Reader（例如 Word、Excel）
- 可以添加新的 Store（例如 Pinecone、Weaviate）
- 可以自定义 KnowledgeBase 实现复杂的检索策略

---

## 六、示例代码

### 完整示例：基础用法

```python
import asyncio
import os
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.rag import TextReader, PDFReader, QdrantStore, SimpleKnowledge

async def main():
    # 1. 创建 Reader
    text_reader = TextReader(chunk_size=1024, split_by="sentence")
    pdf_reader = PDFReader(chunk_size=1024, split_by="sentence")
    
    # 2. 读取文档
    text_docs = await text_reader(
        text="I'm Tony Stark, my password is 123456. "
             "My best friend is James Rhodes."
    )
    pdf_docs = await pdf_reader(pdf_path="example.pdf")
    
    # 3. 创建知识库
    knowledge = SimpleKnowledge(
        embedding_store=QdrantStore(
            location=":memory:",
            collection_name="test_collection",
            dimensions=1024,
        ),
        embedding_model=DashScopeTextEmbedding(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            model_name="text-embedding-v4",
        ),
    )
    
    # 4. 添加文档
    await knowledge.add_documents(text_docs + pdf_docs)
    
    # 5. 检索
    docs = await knowledge.retrieve(
        query="What is Tony Stark's password?",
        limit=3,
        score_threshold=0.7,
    )
    
    # 6. 显示结果
    for doc in docs:
        print(f"Score: {doc.score:.4f}")
        print(f"Content: {doc.metadata.content['text']}")
        print("-" * 50)

asyncio.run(main())
```

### 完整示例：Agent 集成

```python
import asyncio
import os
from agentscope.agent import ReActAgent, UserAgent
from agentscope.embedding import DashScopeTextEmbedding
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.rag import SimpleKnowledge, QdrantStore, TextReader
from agentscope.tool import Toolkit

async def main():
    # 1. 创建知识库
    knowledge = SimpleKnowledge(
        embedding_store=QdrantStore(
            location=":memory:",
            collection_name="user_profile",
            dimensions=1024,
        ),
        embedding_model=DashScopeTextEmbedding(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            model_name="text-embedding-v4",
        ),
    )
    
    # 2. 准备数据
    reader = TextReader(chunk_size=1024, split_by="sentence")
    documents = await reader(
        text=(
            "I'm John Doe, 28 years old. My best friend is James Smith. "
            "I live in San Francisco. I work at OpenAI as a software engineer. "
            "My father is Michael Doe, a doctor. "
            "My mother is Sarah Doe, a teacher."
        )
    )
    await knowledge.add_documents(documents)
    
    # 3. 创建工具集
    toolkit = Toolkit()
    toolkit.register_tool_function(
        knowledge.retrieve_knowledge,
        func_description=(
            "Retrieve relevant information about John Doe. "
            "Adjust score_threshold if no results are found."
        ),
    )
    
    # 4. 创建 Agent
    agent = ReActAgent(
        name="Friday",
        sys_prompt=(
            "You're a helpful assistant. Use the retrieve_knowledge tool "
            "to find information about John Doe."
        ),
        toolkit=toolkit,
        model=DashScopeChatModel(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            model_name="qwen3-max-preview",
        ),
        formatter=DashScopeChatFormatter(),
    )
    
    user = UserAgent(name="User")
    
    # 5. 对话
    msg = Msg("user", "I'm John Doe. Do you know my father?", "user")
    while True:
        msg = await agent(msg)
        msg = await user(msg)
        if msg.get_text_content() == "exit":
            break

asyncio.run(main())
```

### 完整示例：多模态 RAG

```python
import asyncio
import os
from matplotlib import pyplot as plt
from agentscope.agent import ReActAgent
from agentscope.embedding import DashScopeMultiModalEmbedding
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.rag import ImageReader, SimpleKnowledge, QdrantStore

async def main():
    # 1. 创建测试图像
    path_image = "./example.png"
    plt.figure(figsize=(8, 3))
    plt.text(0.5, 0.5, "My name is Ming Li", ha="center", va="center", fontsize=30)
    plt.axis("off")
    plt.savefig(path_image, bbox_inches="tight", pad_inches=0.1)
    plt.close()
    
    # 2. 读取图像
    reader = ImageReader()
    docs = await reader(image_url=path_image)
    
    # 3. 创建多模态知识库
    knowledge = SimpleKnowledge(
        embedding_model=DashScopeMultiModalEmbedding(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            model_name="multimodal-embedding-v1",
            dimensions=1024,
        ),
        embedding_store=QdrantStore(
            location=":memory:",
            collection_name="multimodal",
            dimensions=1024,
        ),
    )
    
    await knowledge.add_documents(docs)
    
    # 4. 创建 VL Agent
    agent = ReActAgent(
        name="Friday",
        sys_prompt="You're a helpful assistant.",
        model=DashScopeChatModel(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            model_name="qwen3-vl-plus",  # 视觉语言模型
        ),
        formatter=DashScopeChatFormatter(),
        knowledge=knowledge,
    )
    
    # 5. 查询
    await agent(Msg("user", "Do you know my name?", "user"))

asyncio.run(main())
```

---

## 七、最佳实践

### 1. 选择合适的 chunk_size

- **小块 (256-512)**: 精确检索，适合问答任务
- **中块 (512-1024)**: 平衡检索精度和上下文
- **大块 (1024-2048)**: 保留更多上下文，适合摘要任务

### 2. 调整 score_threshold

- 开始时使用较低的阈值（0.3-0.5）确保有结果
- 根据检索质量逐步提高阈值
- 对于关键任务，可以使用更高的阈值（0.7-0.9）

### 3. 选择合适的切分策略

- **英文文本**: 优先使用 `split_by="sentence"`
- **中文文本**: 使用 `split_by="char"` 或 `split_by="paragraph"`
- **代码**: 使用 `split_by="paragraph"` 或自定义 Reader

### 4. 向量数据库选择

- **开发/测试**: 使用 `location=":memory:"` 或本地文件
- **生产环境**: 使用远程向量数据库服务
- **大规模部署**: 考虑 Milvus 集群或 Qdrant Cloud

### 5. Embedding 模型选择

- **文本**: 使用专门的文本 embedding 模型
- **多模态**: 使用多模态 embedding 模型（支持图像、视频）
- **多语言**: 选择支持多语言的 embedding 模型

### 6. 性能优化

- **批量处理**: 一次性添加多个文档，提高效率
- **异步调用**: 充分利用 async/await 并发处理
- **索引优化**: 根据向量数据库文档调整索引参数

---

## 八、常见问题

### Q1: 如何持久化向量数据库？

```python
# Qdrant
store = QdrantStore(
    location="./qdrant_data",  # 使用文件路径而非 ":memory:"
    collection_name="my_collection",
    dimensions=1024,
)

# Milvus Lite
store = MilvusLiteStore(
    uri="./milvus_demo.db",  # 本地文件
    collection_name="my_collection",
    dimensions=1024,
)
```

### Q2: 如何避免重复添加文档？

```python
# 使用 Reader 的 get_doc_id() 方法检查文档是否存在
reader = TextReader()
doc_id = reader.get_doc_id(text)

# 在添加前检查 doc_id 是否已存在（需要自己实现检查逻辑）
```

### Q3: 如何自定义 Reader？

```python
from agentscope.rag import ReaderBase, Document, DocMetadata
from agentscope.message import TextBlock

class CustomReader(ReaderBase):
    async def __call__(self, data):
        # 实现自定义的读取和切分逻辑
        chunks = self.custom_split(data)
        
        doc_id = self.get_doc_id(data)
        return [
            Document(
                metadata=DocMetadata(
                    content=TextBlock(type="text", text=chunk),
                    doc_id=doc_id,
                    chunk_id=i,
                    total_chunks=len(chunks),
                ),
            )
            for i, chunk in enumerate(chunks)
        ]
    
    def get_doc_id(self, data):
        import hashlib
        return hashlib.sha256(data.encode()).hexdigest()
    
    def custom_split(self, data):
        # 自定义切分逻辑
        return [data[i:i+100] for i in range(0, len(data), 100)]
```

### Q4: 如何使用其他向量数据库？

继承 `VDBStoreBase` 并实现 `add`, `search`, `delete` 方法：

```python
from agentscope.rag import VDBStoreBase, Document
from agentscope.types import Embedding

class CustomStore(VDBStoreBase):
    def __init__(self, **kwargs):
        # 初始化你的向量数据库客户端
        pass
    
    async def add(self, documents: list[Document], **kwargs):
        # 实现添加逻辑
        pass
    
    async def search(
        self, 
        query_embedding: Embedding, 
        limit: int,
        score_threshold: float | None = None,
        **kwargs
    ) -> list[Document]:
        # 实现搜索逻辑
        pass
    
    async def delete(self, *args, **kwargs):
        # 实现删除逻辑
        pass
```

---

## 九、参考资源

### 官方文档
- [AgentScope 官方文档](https://doc.agentscope.io/)
- [RAG 教程](https://doc.agentscope.io/tutorial/rag.html)

### 示例代码
- `examples/functionality/rag/basic_usage.py` - 基础用法
- `examples/functionality/rag/agentic_usage.py` - Agent 集成
- `examples/functionality/rag/react_agent_integration.py` - ReActAgent 集成
- `examples/functionality/rag/multimodal_rag.py` - 多模态 RAG

### 向量数据库
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Milvus Documentation](https://milvus.io/docs)

---

## 总结

AgentScope 的 RAG 模块提供了一个**工程化、模块化、可扩展**的 RAG 实现方案：

✅ **完整的功能**: 从文档读取、切分、向量化到存储和检索的完整流程  
✅ **灵活的架构**: 解耦设计，易于扩展和定制  
✅ **多种选择**: 支持多种向量数据库、embedding 模型和切分策略  
✅ **易于集成**: 提供两种 Agent 集成方式，满足不同需求  
✅ **多模态支持**: 原生支持文本、图像等多种数据类型  
✅ **生产就绪**: 异步设计、错误处理、性能优化  

无论是简单的问答系统还是复杂的多 Agent 应用，AgentScope RAG 模块都能提供强大的支持！

